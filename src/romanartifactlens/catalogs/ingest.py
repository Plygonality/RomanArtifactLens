"""Read a user CSV/ECSV, including the NGRST-style column aliases.

The private repository Plygonality/NGRST-Discovery-Toolkit was not readable
(HTTP 404) when this adapter was written. Aliases follow the column list in
the RomanArtifactLens brief: ``label``, ``x_centroid``, ``y_centroid``, plus
``area``, ``snr``, ``anomaly_score``, ``anomaly_percentile``, ``ra``, ``dec``,
``known`` and ``reference_id``. Those extra columns are metadata. They do not
set the review status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table

from romanartifactlens.errors import InvalidDataError
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.io.wcsutil import SkyConverter

ID_ALIASES = ("candidate_id", "id", "label", "source_id", "name")
X_ALIASES = ("x", "x_centroid", "x_pix", "xcenter")
Y_ALIASES = ("y", "y_centroid", "y_pix", "ycenter")
RA_ALIASES = ("ra", "ra_deg")
DEC_ALIASES = ("dec", "dec_deg")

METADATA_NOTE = (
    "Non-coordinate catalogue columns are metadata. An anomaly_score column is retained "
    "as an external within-image ranking. It is not used as a significance or as an "
    "artefact probability. The live NGRST-Discovery-Toolkit schema was not readable from "
    "this environment, so this alias list is unverified against that repository."
)


@dataclass
class Candidate:
    candidate_id: str
    x: float | None
    y: float | None
    ra_deg: float | None
    dec_deg: float | None
    catalogue_metadata: dict[str, object] = field(default_factory=dict)


def load_catalog(
    path: str | Path,
    dataset: ImageDataset,
    *,
    coordinate_tolerance_arcsec: float = 0.05,
) -> list[Candidate]:
    file_path = Path(path)
    if not file_path.is_file():
        raise InvalidDataError(f"catalogue file does not exist: {file_path}")
    try:
        table = Table.read(file_path, format=_format_for(file_path))
    except Exception as exc:
        raise InvalidDataError(f"Could not read catalogue {file_path.name}: {exc}") from exc
    if len(table) == 0:
        raise InvalidDataError(f"{file_path.name} has no candidate rows")
    columns = {name.casefold(): name for name in table.colnames}
    id_col = _pick(columns, ID_ALIASES, "candidate id (candidate_id, id, or label)")
    x_col = _pick(columns, X_ALIASES, None)
    y_col = _pick(columns, Y_ALIASES, None)
    ra_col = _pick(columns, RA_ALIASES, None)
    dec_col = _pick(columns, DEC_ALIASES, None)
    if (x_col is None) ^ (y_col is None):
        raise InvalidDataError("Catalogue has only one of x and y. Both pixel coordinates are required.")
    if (ra_col is None) ^ (dec_col is None):
        raise InvalidDataError("Catalogue has only one of ra and dec. Both sky coordinates are required.")
    if x_col is None and ra_col is None:
        raise InvalidDataError(
            "Catalogue is missing coordinates. Provide x and y, or ra and dec when the image has a WCS. "
            f"Columns found: {', '.join(table.colnames)}"
        )
    converter = SkyConverter(dataset.wcs) if dataset.wcs is not None else None
    if x_col is None and converter is None:
        raise InvalidDataError(
            "Catalogue positions are sky coordinates but this image has no WCS. "
            "Supply pixel x and y, or a synthetic/Roman WCS."
        )

    used = {column for column in (id_col, x_col, y_col, ra_col, dec_col) if column}
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for row_index, row in enumerate(table):
        raw_id = row[id_col]
        if raw_id is None or (isinstance(raw_id, float) and not np.isfinite(raw_id)):
            raise InvalidDataError(f"Row {row_index} is missing a candidate id")
        candidate_id = str(raw_id).strip()
        if candidate_id == "" or candidate_id.lower() == "nan":
            raise InvalidDataError(f"Row {row_index} is missing a candidate id")
        if candidate_id in seen:
            raise InvalidDataError(f"Duplicate candidate id {candidate_id!r}")
        seen.add(candidate_id)
        x_value = _float_or_none(row[x_col]) if x_col else None
        y_value = _float_or_none(row[y_col]) if y_col else None
        ra_value = _float_or_none(row[ra_col]) if ra_col else None
        dec_value = _float_or_none(row[dec_col]) if dec_col else None
        if x_value is None and y_value is None and ra_value is None:
            raise InvalidDataError(f"{candidate_id} has no usable coordinates")
        if ra_value is not None:
            ra_value = ra_value % 360.0
        if x_value is None and ra_value is not None and dec_value is not None and converter is not None:
            x_value, y_value = converter.sky_to_pixel(ra_value, dec_value)
        elif (
            x_value is not None
            and y_value is not None
            and ra_value is not None
            and dec_value is not None
            and converter is not None
        ):
            sky_ra, sky_dec = converter.pixel_to_sky(x_value, y_value)
            separation = SkyCoord(ra_value * u.deg, dec_value * u.deg).separation(
                SkyCoord(sky_ra * u.deg, sky_dec * u.deg)
            )
            if separation.arcsec > coordinate_tolerance_arcsec:
                raise InvalidDataError(
                    f"{candidate_id} pixel coordinates convert to ra={sky_ra:.6f} dec={sky_dec:.6f}, "
                    f"which is {separation.arcsec:.4f} arcsec from the catalogue sky position "
                    f"(tolerance {coordinate_tolerance_arcsec} arcsec)."
                )
        if x_value is not None and y_value is not None and converter is not None and ra_value is None:
            ra_value, dec_value = converter.pixel_to_sky(x_value, y_value)
        metadata: dict[str, object] = {"catalogue_row": row_index, "metadata_note": METADATA_NOTE}
        for name in table.colnames:
            if name in used:
                continue
            metadata[name] = _jsonish(row[name])
        if (
            x_value is None
            or y_value is None
            or not np.isfinite(x_value)
            or not np.isfinite(y_value)
        ):
            raise InvalidDataError(f"{candidate_id} produced non-finite pixel coordinates")
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                x=float(x_value),
                y=float(y_value),
                ra_deg=None if ra_value is None else float(ra_value),
                dec_deg=None if dec_value is None else float(dec_value),
                catalogue_metadata=metadata,
            )
        )
    return candidates


def _format_for(path: Path) -> str:
    if path.suffix.lower() == ".ecsv":
        return "ascii.ecsv"
    return "ascii.csv"


def _pick(columns: dict[str, str], aliases: tuple[str, ...], required: str | None) -> str | None:
    found = [columns[alias.casefold()] for alias in aliases if alias.casefold() in columns]
    if not found:
        if required is None:
            return None
        raise InvalidDataError(f"Catalogue is missing {required}")
    if len(found) > 1:
        values_note = ", ".join(found)
        # Two aliases are allowed only when they are the same column name after casefold,
        # which cannot happen. Differing aliases that both exist are an error so a file
        # cannot silently prefer x over a disagreeing x_centroid.
        raise InvalidDataError(
            f"Catalogue has more than one column for the same coordinate role: {values_note}. "
            "Keep a single column."
        )
    return found[0]


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in {"", "nan", "NaN", "None"}:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _jsonish(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not np.isfinite(number):
            return None
        return number
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    text = str(value)
    if text in {"--", ""}:
        return None
    return text
