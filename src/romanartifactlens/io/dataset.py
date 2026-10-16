"""In-memory view of one image. The reader does not write the source file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np


@dataclass
class ImageDataset:
    path: Path
    dataset_kind: str
    data_level: str
    science: np.ndarray
    err: np.ndarray | None
    dq: np.ndarray | None
    dq2: np.ndarray | None = None
    var_poisson: np.ndarray | None = None
    var_rnoise: np.ndarray | None = None
    var_flat: np.ndarray | None = None
    units: str | None = None
    units_note: str = ""
    wcs: Any | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    declaration: str | None = None
    uncertainty_model: str | None = None
    _closer: Callable[[], None] | None = field(default=None, repr=False)

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.science.shape[0]), int(self.science.shape[1])

    def close(self) -> None:
        if self._closer is not None:
            closer = self._closer
            self._closer = None
            closer()

    def __enter__(self) -> ImageDataset:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
