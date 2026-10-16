"""Display stretch. The returned array is not the science array."""

from __future__ import annotations

import numpy as np


def asinh_display(science: np.ndarray, coverage: np.ndarray | None = None) -> tuple[np.ndarray, dict[str, float | None]]:
    """Map finite covered pixels with an asinh stretch into ``[0, 1]``."""

    values = np.asarray(science, dtype=np.float64)
    valid = np.isfinite(values)
    if coverage is not None:
        valid &= coverage
    display = np.full(values.shape, np.nan, dtype=np.float64)
    if int(np.count_nonzero(valid)) < 5:
        return display, {"vmin": None, "vmax": None, "method": "asinh_percentile"}
    sample = values[valid]
    vmin = float(np.nanpercentile(sample, 1.0))
    vmax = float(np.nanpercentile(sample, 99.0))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin = float(np.min(sample))
        vmax = float(np.max(sample))
    if vmax <= vmin:
        display[valid] = 0.5
        return display, {"vmin": vmin, "vmax": vmax, "method": "asinh_percentile"}
    span = vmax - vmin
    scaled = np.clip((values - vmin) / span, 0.0, 1.0)
    stretched = np.arcsinh(scaled * 10.0) / np.arcsinh(10.0)
    display[valid] = stretched[valid]
    return display, {"vmin": vmin, "vmax": vmax, "method": "asinh_percentile"}
