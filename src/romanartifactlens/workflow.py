"""In-process analyse path shared by the CLI and the tests."""

from __future__ import annotations

from pathlib import Path

from romanartifactlens.catalogs.ingest import load_catalog
from romanartifactlens.dq.definitions import FlagDictionary, load_flag_dictionary
from romanartifactlens.errors import PartialEvidenceError
from romanartifactlens.evidence.evaluate import evaluate_candidate
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.io.open import open_dataset
from romanartifactlens.reports.export import write_report_bundle
from romanartifactlens.settings import AnalysisSettings


def analyze_files(
    image: Path,
    catalog: Path,
    output: Path,
    settings: AnalysisSettings,
    *,
    asserted_level: str | None = None,
    command: str = "",
    dictionary: FlagDictionary | None = None,
) -> dict[str, object]:
    settings.validate()
    flag_dictionary = dictionary or load_flag_dictionary()
    with open_dataset(image, asserted_level=asserted_level) as dataset:
        return analyze_dataset(
            dataset,
            catalog,
            output,
            settings,
            command=command,
            dictionary=flag_dictionary,
            extra_inputs=_sidecar_inputs(catalog),
        )


def analyze_dataset(
    dataset: ImageDataset,
    catalog: Path,
    output: Path,
    settings: AnalysisSettings,
    *,
    command: str,
    dictionary: FlagDictionary,
    extra_inputs: list[Path] | None = None,
) -> dict[str, object]:
    candidates = load_catalog(
        catalog,
        dataset,
        coordinate_tolerance_arcsec=settings.coordinate_tolerance_arcsec,
    )
    packets = [
        evaluate_candidate(dataset, candidate, settings, dictionary) for candidate in candidates
    ]
    inputs = [dataset.path, catalog]
    if extra_inputs:
        inputs.extend(extra_inputs)
    manifest = write_report_bundle(
        output,
        dataset,
        packets,
        inputs=inputs,
        settings=settings,
        dictionary=dictionary,
        command=command,
    )
    if settings.strict and strict_failure(packets, settings):
        raise PartialEvidenceError(
            "Strict mode: at least one candidate is INSUFFICIENT_EVIDENCE or is missing DQ. "
            "An unrequested PSF comparison may stay NOT_EVALUATED. "
            "A requested PSF adapter that does not measure a model also fails strict mode."
        )
    return {"manifest": manifest, "packets": packets}


def strict_failure(packets: list[object], settings: AnalysisSettings) -> bool:
    for packet in packets:
        report = packet.report  # type: ignore[attr-defined]
        if report["overall_review_status"] == "INSUFFICIENT_EVIDENCE":
            return True
        for item in report["evidence"]:
            if item["code"] == "RAL-DQ-001" and item["status"] == "MISSING_DQ":
                return True
        if settings.psf_adapter != "none":
            for item in report["evidence"]:
                if item["code"] == "RAL-PSF-020" and item["status"] != "MEASURED":
                    return True
    return False


def _sidecar_inputs(catalog: Path) -> list[Path]:
    found: list[Path] = []
    sibling = catalog.with_suffix(".json")
    run_json = catalog.parent / "run.json"
    for path in (sibling, run_json):
        if path.is_file() and path not in found:
            found.append(path)
    return found
