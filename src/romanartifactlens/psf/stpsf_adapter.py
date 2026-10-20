"""Optional STPSF path. Missing calibration context fails closed."""

from __future__ import annotations

from typing import Any

import numpy as np

from romanartifactlens.errors import OptionalDependencyError


def stpsf_requirements(meta: dict[str, Any]) -> str | None:
    """Return a missing-context reason, or None when filter, detector, and position exist."""

    if not meta.get("optical_element"):
        return "optical_element (filter) is missing"
    if not meta.get("detector"):
        return "detector is missing"
    return None


def compute_stpsf(
    *,
    optical_element: str,
    detector: str,
    x: float,
    y: float,
    fov_pixels: int,
) -> np.ndarray:
    """Call installed STPSF. Exceptions propagate so the caller can fail closed."""

    try:
        import stpsf
    except ImportError as exc:
        raise OptionalDependencyError(
            "STPSF is not installed. Install the psf extra or leave --psf none. "
            "A Gaussian toy is not substituted."
        ) from exc
    instrument = stpsf.Roman()
    instrument.filter = optical_element
    instrument.detector = detector
    # 0-based pixel centers, matching this package's catalogue convention.
    # Confirm against the installed STPSF notes if a residual looks shifted by one pixel.
    instrument.detector_position = (float(x), float(y))
    hdul = instrument.calc_psf(fov_pixels=int(fov_pixels), oversample=1)
    image = np.array(hdul[0].data, dtype=np.float64)
    return image
