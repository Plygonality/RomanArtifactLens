"""Pixel-center apertures. A pixel is inside when its center is inside the radius."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CircularRegion:
    """On-image boolean mask plus the count of pixel centers that fell off the image."""

    mask: np.ndarray
    n_on_image: int
    n_off_image: int

    @property
    def n_geometric(self) -> int:
        return self.n_on_image + self.n_off_image

    @property
    def off_image_fraction(self) -> float | None:
        total = self.n_geometric
        if total == 0:
            return None
        return self.n_off_image / total


def circular_region(
    shape: tuple[int, int],
    x: float,
    y: float,
    r_outer: float,
    r_inner: float = 0.0,
) -> CircularRegion:
    """Select pixel centers.

    Coordinates are 0-based pixel centers: array index ``[row, col]`` has center
    ``(x=col, y=row)``. The aperture is ``distance <= r_outer``. An annulus is
    ``r_inner < distance <= r_outer``. The boundary belongs to the inner region.
    """

    ny, nx = shape
    if r_outer < 0 or r_inner < 0:
        raise ValueError("radii must be non-negative")
    col0 = math.floor(x - r_outer)
    col1 = math.ceil(x + r_outer)
    row0 = math.floor(y - r_outer)
    row1 = math.ceil(y + r_outer)
    cols = np.arange(col0, col1 + 1)
    rows = np.arange(row0, row1 + 1)
    if cols.size == 0 or rows.size == 0:
        return CircularRegion(np.zeros(shape, dtype=bool), 0, 0)
    cc, rr = np.meshgrid(cols, rows)
    distance = np.hypot(cc - x, rr - y)
    if r_inner <= 0:
        inside = distance <= (r_outer + 1e-9)
    else:
        inside = (distance > r_inner) & (distance <= (r_outer + 1e-9))
    on_image = inside & (rr >= 0) & (rr < ny) & (cc >= 0) & (cc < nx)
    mask = np.zeros(shape, dtype=bool)
    if np.any(on_image):
        mask[rr[on_image], cc[on_image]] = True
    n_on = int(np.count_nonzero(on_image))
    n_off = int(np.count_nonzero(inside)) - n_on
    return CircularRegion(mask=mask, n_on_image=n_on, n_off_image=n_off)


def nearest_pixel(x: float, y: float) -> tuple[int, int]:
    """Nearest pixel center using NumPy round-half-to-even."""

    return int(np.round(x)), int(np.round(y))
