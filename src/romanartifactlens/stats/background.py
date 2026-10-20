"""Robust local background from an annulus of valid pixels."""

from __future__ import annotations

import numpy as np


def estimate_background(
    values: np.ndarray,
    *,
    method: str,
    sigma: float,
    min_pixels: int,
) -> dict[str, object]:
    sample = np.asarray(values, dtype=np.float64)
    sample = sample[np.isfinite(sample)]
    n_input = int(sample.size)
    if n_input < min_pixels:
        return {
            "status": "INSUFFICIENT_SAMPLES",
            "method": method,
            "n_valid": n_input,
            "n_used": 0,
            "value": None,
            "scale": None,
            "min_pixels": min_pixels,
        }
    used = sample
    if method == "sigma_clip_median":
        used = _sigma_clip(sample, sigma=sigma, min_pixels=min_pixels)
    elif method != "median":
        raise ValueError(f"unknown background method {method}")
    if used.size < min_pixels:
        return {
            "status": "INSUFFICIENT_SAMPLES",
            "method": method,
            "n_valid": n_input,
            "n_used": int(used.size),
            "value": None,
            "scale": None,
            "min_pixels": min_pixels,
        }
    median = float(np.median(used))
    mad = float(np.median(np.abs(used - median)))
    scale = float(1.4826 * mad)
    return {
        "status": "MEASURED",
        "method": method,
        "n_valid": n_input,
        "n_used": int(used.size),
        "value": median,
        "scale": scale,
        "min_pixels": min_pixels,
    }


def _sigma_clip(sample: np.ndarray, sigma: float, min_pixels: int) -> np.ndarray:
    data = sample
    for _ in range(5):
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        scale = 1.4826 * mad
        if scale == 0 or not np.isfinite(scale):
            return data
        keep = np.abs(data - median) <= sigma * scale
        if int(np.count_nonzero(keep)) < min_pixels or int(np.count_nonzero(keep)) == data.size:
            return data
        data = data[keep]
    return data
