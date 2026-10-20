"""Shape measurements on a local cutout, using photutils segmentation."""

from __future__ import annotations

import inspect
import math
from typing import Any

import numpy as np
from photutils.segmentation import SourceCatalog, detect_sources


def measure_morphology(
    science: np.ndarray,
    *,
    coverage: np.ndarray,
    bad: np.ndarray,
    background: float | None,
    noise_scale: float | None,
    nsigma: float,
    local_x: float,
    local_y: float,
) -> dict[str, object]:
    """Segment pixels above ``background + nsigma * scale`` and describe the central object."""

    result: dict[str, object] = {
        "status": "NOT_EVALUATED",
        "reason": "BACKGROUND_UNAVAILABLE",
        "method": "photutils.segmentation.detect_sources",
        "area_px": None,
        "ellipticity": None,
        "elongation": None,
        "axis_ratio": None,
        "orientation_rad": None,
        "eccentricity": None,
        "central_concentration": None,
        "n_pixels_above_threshold": 0,
        "isolated_pixel": False,
    }
    if background is None or not np.isfinite(background):
        return result
    scale = 0.0 if noise_scale is None or not np.isfinite(noise_scale) else float(noise_scale)
    threshold = float(background + nsigma * scale)
    data = np.array(science, dtype=np.float64, copy=True)
    mask = (~coverage) | bad | ~np.isfinite(data)
    data[mask] = threshold
    try:
        segment = _detect(data, threshold, mask)
    except Exception as exc:
        result["reason"] = f"SEGMENTATION_FAILED: {exc}"
        return result
    above = (~mask) & np.isfinite(science) & (np.asarray(science) > threshold)
    n_above = int(np.count_nonzero(above))
    result["n_pixels_above_threshold"] = n_above
    finite = (~mask) & np.isfinite(science)
    excess = np.asarray(science, dtype=np.float64) - background
    positive = finite & (excess > 0)
    positive_sum = float(np.sum(excess[positive])) if np.any(positive) else 0.0
    row = int(np.round(local_y))
    col = int(np.round(local_x))
    on_cutout = 0 <= row < science.shape[0] and 0 <= col < science.shape[1]
    central_excess = float(excess[row, col]) if on_cutout and np.isfinite(excess[row, col]) else None
    if positive_sum > 0 and central_excess is not None and central_excess > 0:
        result["central_concentration"] = central_excess / positive_sum
    if segment is None or n_above == 0:
        result["status"] = "MEASURED"
        result["reason"] = "NO_PIXELS_ABOVE_THRESHOLD"
        result["isolated_pixel"] = False
        return result
    if not on_cutout:
        result["reason"] = "CENTRAL_PIXEL_OFF_CUTOUT"
        return result
    label = int(segment.data[row, col])
    if label == 0:
        result["status"] = "MEASURED"
        result["reason"] = "CENTRAL_PIXEL_NOT_IN_SEGMENT"
        return result
    try:
        catalog = SourceCatalog(data, segment, mask=mask)
        source = _source_by_label(catalog, label)
        area = _plain(getattr(source, "area", None))
        ellipticity = _plain(getattr(source, "ellipticity", None))
        elongation = _plain(getattr(source, "elongation", None))
        orientation = _angle_radians(getattr(source, "orientation", None))
        eccentricity = _plain(getattr(source, "eccentricity", None))
    except Exception as exc:
        result["status"] = "NOT_EVALUATED"
        result["reason"] = f"SOURCECATALOG_FAILED: {exc}"
        return result
    axis_ratio = None
    if area is not None and area <= 1:
        ellipticity = None
        orientation = None
        elongation = None
    elif elongation is not None and elongation > 0:
        axis_ratio = 1.0 / elongation
    concentration = result["central_concentration"]
    isolated = bool(
        area == 1
        or (
            n_above == 1
            and isinstance(concentration, float)
            and concentration >= 0.85
        )
    )
    result.update(
        {
            "status": "MEASURED",
            "reason": "CENTRAL_SEGMENT",
            "area_px": area,
            "ellipticity": ellipticity,
            "elongation": elongation,
            "axis_ratio": axis_ratio,
            "orientation_rad": orientation,
            "eccentricity": eccentricity,
            "isolated_pixel": isolated,
        }
    )
    return result


def _detect(data: np.ndarray, threshold: float, mask: np.ndarray) -> Any:
    signature = inspect.signature(detect_sources)
    kwargs: dict[str, object] = {"mask": mask, "connectivity": 8}
    if "n_pixels" in signature.parameters:
        kwargs["n_pixels"] = 1
    else:
        kwargs["npixels"] = 1
    return detect_sources(data, threshold, **kwargs)


def _source_by_label(catalog: Any, label: int) -> Any:
    labels = list(getattr(catalog, "labels", []))
    if label not in labels:
        raise RuntimeError(f"segment label {label} missing from SourceCatalog")
    return catalog[labels.index(label)]


def _angle_radians(value: object) -> float | None:
    if value is None:
        return None
    unit = getattr(value, "unit", None)
    raw = getattr(value, "value", value)
    number = _plain(raw)
    if number is None:
        return None
    if unit is not None and "deg" in str(unit):
        return float(math.radians(number))
    return number


def _plain(value: object) -> float | None:
    if value is None:
        return None
    array = np.asarray(value, dtype=float)
    if array.shape != ():
        return None
    number = float(array)
    if not np.isfinite(number):
        return None
    return number
