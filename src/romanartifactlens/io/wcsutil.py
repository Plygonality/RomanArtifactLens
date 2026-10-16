"""Pixel/sky conversions.

Synthetic NPZ files store a TAN WCS whose CRPIX is 0-based (pixel centers).
Astropy's FITS WCS stores CRPIX 1-based. The high-level ``pixel_to_world`` API
then accepts the same 0-based ``(x, y)`` used by candidate catalogues.
"""

from __future__ import annotations

from typing import Any

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS


def tan_wcs_from_arrays(
    crpix_xy: np.ndarray,
    crval_deg: np.ndarray,
    cd: np.ndarray,
) -> WCS:
    """Build a TAN WCS. ``crpix_xy`` is 0-based ``(x, y)`` of the reference pixel center."""

    transform = WCS(naxis=2)
    transform.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    transform.wcs.cunit = ["deg", "deg"]
    transform.wcs.crpix = [float(crpix_xy[0]) + 1.0, float(crpix_xy[1]) + 1.0]
    transform.wcs.crval = [float(crval_deg[0]), float(crval_deg[1])]
    transform.wcs.cdelt = [1.0, 1.0]
    transform.wcs.pc = np.array(cd, dtype=float)
    transform.wcs.set()
    return transform


class SkyConverter:
    """Thin adapter over astropy WCS or gwcs."""

    def __init__(self, wcs: Any) -> None:
        self.wcs = wcs

    def pixel_to_sky(self, x: float, y: float) -> tuple[float, float]:
        sky = self.wcs.pixel_to_world(x, y)
        ra = float(np.asarray(sky.ra.deg, dtype=float)) % 360.0
        dec = float(np.asarray(sky.dec.deg, dtype=float))
        return ra, dec

    def sky_to_pixel(self, ra_deg: float, dec_deg: float) -> tuple[float, float]:
        sky = SkyCoord((float(ra_deg) % 360.0) * u.deg, float(dec_deg) * u.deg, frame="icrs")
        x_value, y_value = self.wcs.world_to_pixel(sky)
        return float(np.asarray(x_value)), float(np.asarray(y_value))

    def available(self) -> bool:
        return self.wcs is not None
