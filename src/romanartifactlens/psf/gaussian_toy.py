"""Circular Gaussian toy fit for synthetic fixtures only."""

from __future__ import annotations

import numpy as np


def fit_circular_gaussian(
    science: np.ndarray,
    coverage: np.ndarray,
    bad: np.ndarray,
    x: float,
    y: float,
    sigma: float,
) -> dict[str, object]:
    """Fit amplitude and background at a fixed sigma, with a small position grid.

    ``x`` and ``y`` are in the same index frame as ``science`` (cutout pixels).
    """

    if sigma <= 0:
        return {"status": "NOT_EVALUATED", "reason": "NONPOSITIVE_SIGMA"}
    usable = coverage & ~bad & np.isfinite(science)
    if int(np.count_nonzero(usable)) < 8:
        return {"status": "NOT_EVALUATED", "reason": "TOO_FEW_PIXELS"}
    best: dict[str, object] | None = None
    offsets = np.linspace(-1.0, 1.0, 21)
    yy, xx = np.indices(science.shape)
    for dy in offsets:
        for dx in offsets:
            model_core = np.exp(-0.5 * ((xx - (x + dx)) ** 2 + (yy - (y + dy)) ** 2) / sigma**2)
            design = np.column_stack(
                [model_core[usable], np.ones(int(np.count_nonzero(usable)), dtype=np.float64)]
            )
            coeff, residuals, _rank, _singular = np.linalg.lstsq(design, science[usable], rcond=None)
            amplitude = float(coeff[0])
            background = float(coeff[1])
            model = amplitude * model_core + background
            residual = np.asarray(science, dtype=np.float64) - model
            rss = float(np.sum(residual[usable] ** 2))
            if best is None or rss < float(best["rss"]):
                best = {
                    "status": "MEASURED",
                    "reason": "SYNTHETIC_GAUSSIAN_TOY",
                    "amplitude": amplitude,
                    "background": background,
                    "dx_px": float(dx),
                    "dy_px": float(dy),
                    "sigma_px": float(sigma),
                    "rss": rss,
                    "rmse": float(np.sqrt(rss / int(np.count_nonzero(usable)))),
                    "n_pixels": int(np.count_nonzero(usable)),
                    "model": model,
                    "residual": residual,
                    "roman_calibrated": False,
                    "model_name": "synthetic_gaussian_toy",
                }
    assert best is not None
    return best
