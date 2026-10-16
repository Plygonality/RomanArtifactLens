"""Write the evidence bundle: JSON, CSV/ECSV, PNG, and HTML."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from astropy.table import Table

from romanartifactlens.dq.definitions import FlagDictionary
from romanartifactlens.evidence.evaluate import CandidatePacket
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.jsonutil import json_safe
from romanartifactlens.reports.figures import write_candidate_figures
from romanartifactlens.reports.html_report import write_candidate_html, write_index_html
from romanartifactlens.reports.provenance import file_record, software_versions, utc_now
from romanartifactlens.settings import AnalysisSettings

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def write_report_bundle(
    output: Path,
    dataset: ImageDataset,
    packets: list[CandidatePacket],
    *,
    inputs: list[Path],
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
    command: str,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(dataset, packets, inputs, settings, dictionary, command)
    rows = []
    for packet in packets:
        safe = _safe_id(packet.report["candidate_id"])
        folder = output / "candidates" / safe
        folder.mkdir(parents=True, exist_ok=True)
        figures = write_candidate_figures(packet, folder, dataset.units)
        packet.report["figures"] = figures
        evidence_path = folder / "evidence.json"
        evidence_path.write_text(_dumps(packet.report), encoding="utf-8")
        review_path = folder / "review.html"
        write_candidate_html(review_path, packet.report, figures, manifest)
        rows.append(_table_row(packet, f"candidates/{safe}/review.html"))
    manifest["candidates"] = rows
    (output / "manifest.json").write_text(_dumps(manifest), encoding="utf-8")
    _write_table(output, rows)
    write_index_html(output / "index.html", manifest, rows)
    return manifest


def rebuild_html(output: Path) -> None:
    """Rebuild HTML from evidence JSON already in ``output``."""

    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        from romanartifactlens.errors import InvalidDataError

        raise InvalidDataError(f"No manifest.json in {output}. Run analyze first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for folder in sorted((output / "candidates").glob("*")):
        evidence_path = folder / "evidence.json"
        if not evidence_path.is_file():
            continue
        report = json.loads(evidence_path.read_text(encoding="utf-8"))
        figures = {
            key: value
            for key, value in dict(report.get("figures") or {}).items()
            if isinstance(value, str)
        }
        write_candidate_html(folder / "review.html", report, figures, manifest)
        rows.append(
            _table_row_from_report(report, f"candidates/{folder.name}/review.html")
        )
    if not rows and manifest.get("candidates"):
        rows = list(manifest["candidates"])
    write_index_html(output / "index.html", manifest, rows)


def _manifest(
    dataset: ImageDataset,
    packets: list[CandidatePacket],
    inputs: list[Path],
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
    command: str,
) -> dict[str, Any]:
    limitations = [
        "v0.1 does not compare multiple exposures and does not join an L3 context map to L2 inputs.",
        dataset.units_note,
    ]
    if dataset.dataset_kind == "SYNTHETIC_TEST":
        limitations.insert(
            0,
            "SYNTHETIC_TEST. Input arrays are a labelled fixture, not a Roman observation.",
        )
    return {
        "schema_version": "1.0.0",
        "created_utc": utc_now(),
        "command": command,
        "software": software_versions(),
        "dataset_kind": dataset.dataset_kind,
        "data_level": dataset.data_level,
        "units": dataset.units,
        "units_note": dataset.units_note,
        "coordinate_convention": (
            "0-based pixel centers; x = column; y = row; array index is [y, x]. "
            "Sky conversions use the file WCS (astropy or gwcs) with that same 0-based origin."
        ),
        "seed": dataset.meta.get("seed"),
        "inputs": [file_record(path) for path in inputs],
        "flag_definitions": dictionary.to_dict(),
        "reference_model": {
            "psf_adapter": settings.psf_adapter,
            "roman_calibrated_psf": False,
            "note": "A synthetic Gaussian is never recorded as a Roman PSF.",
        },
        "analysis_settings": settings.to_dict(),
        "candidate_ids": [packet.report["candidate_id"] for packet in packets],
        "limitations": [item for item in limitations if item],
        "roman_validation": dataset.meta.get("roman_validation"),
        "dataset_meta": {
            key: dataset.meta.get(key)
            for key in (
                "model_type",
                "detector",
                "optical_element",
                "filename",
                "calibration_software_name",
                "calibration_software_version",
                "origin",
                "schema_allowed_science_units",
                "validation_note",
                "roman_datamodels_version",
            )
        },
    }


def _table_row(packet: CandidatePacket, href: str) -> dict[str, Any]:
    return _table_row_from_report(packet.report, href)


def _table_row_from_report(report: dict[str, Any], href: str) -> dict[str, Any]:
    central = (report.get("dq_summary") or {}).get("central") or {}
    aperture = (report.get("dq_summary") or {}).get("aperture") or {}
    uncertainty = (report.get("measurements") or {}).get("uncertainty") or {}
    morphology = (report.get("measurements") or {}).get("morphology") or {}
    background = (report.get("measurements") or {}).get("background") or {}
    flags = list(central.get("flags") or [])
    unknown = list(central.get("unknown_bits") or [])
    return {
        "candidate_id": report["candidate_id"],
        "x": (report.get("position") or {}).get("x"),
        "y": (report.get("position") or {}).get("y"),
        "ra_deg": (report.get("position") or {}).get("ra_deg"),
        "dec_deg": (report.get("position") or {}).get("dec_deg"),
        "overall_review_status": report["overall_review_status"],
        "central_flags": " ".join(flags + [f"UNKNOWN_DQ_BIT_{bit}" for bit in unknown]),
        "do_not_use_fraction": (aperture or {}).get("do_not_use_fraction"),
        "background": background.get("value"),
        "background_status": background.get("status"),
        "significance": uncertainty.get("significance"),
        "significance_status": uncertainty.get("status"),
        "isolated_pixel_heuristic": bool(morphology.get("isolated_pixel")),
        "href": href,
    }


def _write_table(output: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "candidate_id",
        "x",
        "y",
        "ra_deg",
        "dec_deg",
        "overall_review_status",
        "central_flags",
        "do_not_use_fraction",
        "background",
        "background_status",
        "significance",
        "significance_status",
        "isolated_pixel_heuristic",
        "href",
    ]
    csv_path = output / "evidence_table.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})
    columns: dict[str, object] = {}
    for key in fieldnames:
        values = [row.get(key) for row in rows]
        if values and all(isinstance(value, bool) for value in values):
            columns[key] = values
            continue
        numeric = []
        is_numeric = True
        for value in values:
            if value is None or isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric.append(np.nan if value is None else float(value))
            else:
                is_numeric = False
                break
        if is_numeric:
            columns[key] = np.ma.masked_invalid(np.array(numeric, dtype=float))
        else:
            columns[key] = ["" if value is None else str(value) for value in values]
    Table(columns).write(output / "evidence_table.ecsv", format="ascii.ecsv", overwrite=True)


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"


def _safe_id(candidate_id: str) -> str:
    cleaned = _SAFE.sub("_", candidate_id).strip("._")
    if not cleaned:
        from romanartifactlens.errors import InvalidDataError

        raise InvalidDataError(f"candidate id {candidate_id!r} cannot be used as a directory name")
    return cleaned
