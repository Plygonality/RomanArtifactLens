"""Bounded cutouts. Off-image samples are NaN, never a fake zero-DQ pixel."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from romanartifactlens.io.dataset import ImageDataset


@dataclass
class Cutout:
    science: np.ndarray
    err: np.ndarray | None
    dq: np.ndarray | None
    dq2: np.ndarray | None
    coverage: np.ndarray
    origin_x: int
    origin_y: int
    candidate_x: float
    candidate_y: float

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.science.shape[0]), int(self.science.shape[1])


def extract_cutout(dataset: ImageDataset, x: float, y: float, radius_px: float) -> Cutout:
    """Return a square window centered on the candidate.

    The window is copied. The parent image is not modified. Pixels outside the
    image are NaN in the science and error arrays. The coverage mask is False
    there, and the DQ window uses 0 only where coverage is True.
    """

    half = int(np.ceil(radius_px))
    size = half * 2 + 1
    center_col = int(np.floor(x))
    center_row = int(np.floor(y))
    origin_x = center_col - half
    origin_y = center_row - half
    science = np.full((size, size), np.nan, dtype=np.float64)
    coverage = np.zeros((size, size), dtype=bool)
    err = None if dataset.err is None else np.full((size, size), np.nan, dtype=np.float64)
    dq = None if dataset.dq is None else np.zeros((size, size), dtype=np.uint32)
    dq2 = None if dataset.dq2 is None else np.zeros((size, size), dtype=np.uint32)
    ny, nx = dataset.shape
    src_row0 = max(origin_y, 0)
    src_row1 = min(origin_y + size, ny)
    src_col0 = max(origin_x, 0)
    src_col1 = min(origin_x + size, nx)
    if src_row1 > src_row0 and src_col1 > src_col0:
        dst_row0 = src_row0 - origin_y
        dst_col0 = src_col0 - origin_x
        dst_row1 = dst_row0 + (src_row1 - src_row0)
        dst_col1 = dst_col0 + (src_col1 - src_col0)
        science[dst_row0:dst_row1, dst_col0:dst_col1] = np.asarray(
            dataset.science[src_row0:src_row1, src_col0:src_col1], dtype=np.float64
        )
        coverage[dst_row0:dst_row1, dst_col0:dst_col1] = True
        if err is not None and dataset.err is not None:
            err[dst_row0:dst_row1, dst_col0:dst_col1] = np.asarray(
                dataset.err[src_row0:src_row1, src_col0:src_col1], dtype=np.float64
            )
        if dq is not None and dataset.dq is not None:
            dq[dst_row0:dst_row1, dst_col0:dst_col1] = np.asarray(
                dataset.dq[src_row0:src_row1, src_col0:src_col1], dtype=np.uint32
            )
        if dq2 is not None and dataset.dq2 is not None:
            dq2[dst_row0:dst_row1, dst_col0:dst_col1] = np.asarray(
                dataset.dq2[src_row0:src_row1, src_col0:src_col1], dtype=np.uint32
            )
    return Cutout(
        science=science,
        err=err,
        dq=dq,
        dq2=dq2,
        coverage=coverage,
        origin_x=origin_x,
        origin_y=origin_y,
        candidate_x=float(x),
        candidate_y=float(y),
    )
