"""Dispatch on suffix. ``.asdf`` never falls through to the NPZ reader."""

from __future__ import annotations

from pathlib import Path

from romanartifactlens.errors import InvalidDataError, UnsupportedDatamodelError
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.io.npz_reader import read_npz
from romanartifactlens.io.roman_asdf import read_roman_asdf


def open_dataset(path: str | Path, asserted_level: str | None = None) -> ImageDataset:
    file_path = Path(path)
    if not file_path.is_file():
        raise InvalidDataError(f"image file does not exist: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix == ".npz":
        dataset = read_npz(file_path)
        if asserted_level is not None:
            claimed = asserted_level.upper()
            actual = dataset.data_level.upper()
            if claimed != actual:
                raise UnsupportedDatamodelError(
                    f"Requested data level {asserted_level} but the NPZ declares data_level "
                    f"{dataset.data_level}. Synthetic files are not promoted to Roman L2."
                )
        return dataset
    if suffix == ".asdf":
        return read_roman_asdf(file_path, asserted_level=asserted_level)
    raise InvalidDataError(
        f"Unsupported file suffix {suffix!r}. v0.1 reads a SYNTHETIC_TEST .npz or a Roman "
        ".asdf opened by roman_datamodels."
    )
