"""Synthetic NPZ reader.

A file must declare ``SYNTHETIC_TEST``. Roman observation identifiers and
calibrated unit strings are rejected so a fixture cannot be mistaken for an
exposure.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from romanartifactlens.errors import InvalidDataError
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.io.wcsutil import tan_wcs_from_arrays

_CALIBRATED_UNITS = {
    "dn/s",
    "dn / s",
    "mjy/sr",
    "mjy / sr",
    "mjy.sr**-1",
    "electron/s",
    "e-/s",
}


def _scalar_str(value: object, label: str) -> str:
    array = np.asarray(value)
    if array.shape == ():
        return str(array.item())
    if array.size == 1:
        return str(array.reshape(-1)[0])
    raise InvalidDataError(f"{label} must be a single string, got shape {array.shape}")


def _optional_array(handle: np.lib.npyio.NpzFile, key: str, shape: tuple[int, int]) -> np.ndarray | None:
    if key not in handle.files:
        return None
    array = np.asarray(handle[key])
    if array.shape != shape:
        raise InvalidDataError(
            f"NPZ array '{key}' has shape {array.shape}, which does not match science {shape}"
        )
    return array


def read_npz(path: Path) -> ImageDataset:
    if not path.is_file():
        raise InvalidDataError(f"image file does not exist: {path}")
    handle = np.load(path, allow_pickle=False)
    try:
        if "declaration" not in handle.files:
            raise InvalidDataError(
                "Synthetic NPZ is missing 'declaration'. RomanArtifactLens requires the "
                "string SYNTHETIC_TEST and will not treat an undeclared array as Roman data."
            )
        declaration = _scalar_str(handle["declaration"], "declaration")
        if declaration != "SYNTHETIC_TEST":
            raise InvalidDataError(
                f"NPZ declaration is {declaration!r}. Only SYNTHETIC_TEST is accepted. "
                "This reader does not relabel arrays as Roman observations."
            )
        if "science" not in handle.files:
            raise InvalidDataError("NPZ is missing the science array")
        science = np.asarray(handle["science"])
        if science.ndim != 2:
            raise InvalidDataError(
                f"science must be a 2-D image, got ndim={science.ndim} shape={science.shape}"
            )
        if not np.issubdtype(science.dtype, np.number):
            raise InvalidDataError(f"science dtype {science.dtype} is not numeric")
        shape = (int(science.shape[0]), int(science.shape[1]))
        err = _optional_array(handle, "err", shape)
        dq = _optional_array(handle, "dq", shape)
        dq2 = _optional_array(handle, "dq2", shape)
        var_poisson = _optional_array(handle, "var_poisson", shape)
        var_rnoise = _optional_array(handle, "var_rnoise", shape)
        var_flat = _optional_array(handle, "var_flat", shape)
        if dq is not None and not np.issubdtype(dq.dtype, np.integer):
            raise InvalidDataError("dq must be an integer bitmask array")
        if dq is not None:
            if int(np.min(dq)) < 0 or int(np.max(dq)) > 0xFFFFFFFF:
                raise InvalidDataError("dq values must fit in an unsigned 32-bit bitmask")
            dq = np.asarray(dq, dtype=np.uint32)
        if dq2 is not None:
            if not np.issubdtype(dq2.dtype, np.integer):
                raise InvalidDataError("dq2 must be an integer array")
            dq2 = np.asarray(dq2, dtype=np.uint32)
        units = "synthetic_counts"
        if "units" in handle.files:
            units = _scalar_str(handle["units"], "units")
        if units.strip().lower() in _CALIBRATED_UNITS:
            raise InvalidDataError(
                f"Synthetic NPZ units are {units!r}. Use a synthetic_* unit string. "
                "Calibrated Roman units are not applied to a SYNTHETIC_TEST file."
            )
        if not units.lower().startswith("synthetic") and units.lower() != "dimensionless":
            raise InvalidDataError(
                f"Synthetic NPZ units must start with 'synthetic' or be 'dimensionless', got {units!r}"
            )
        data_level = "SYNTHETIC"
        if "data_level" in handle.files:
            data_level = _scalar_str(handle["data_level"], "data_level")
        uncertainty_model = None
        if "uncertainty_model" in handle.files:
            uncertainty_model = _scalar_str(handle["uncertainty_model"], "uncertainty_model")
        notes = ""
        if "notes" in handle.files:
            notes = _scalar_str(handle["notes"], "notes")
        seed = None
        if "seed" in handle.files:
            seed = int(np.asarray(handle["seed"]).reshape(-1)[0])
        wcs = None
        if all(key in handle.files for key in ("wcs_crpix", "wcs_crval", "wcs_cd")):
            wcs = tan_wcs_from_arrays(handle["wcs_crpix"], handle["wcs_crval"], handle["wcs_cd"])
        meta = {
            "notes": notes,
            "seed": seed,
            "format": "npz",
            "arrays": _array_summary(handle),
            "roman_validation": "not_applicable_synthetic_test",
        }
        # Copy the planes we keep so closing the NPZ handle cannot invalidate them.
        dataset = ImageDataset(
            path=path,
            dataset_kind="SYNTHETIC_TEST",
            data_level=data_level,
            science=np.array(science, copy=True),
            err=None if err is None else np.array(err, dtype=np.float64, copy=True),
            dq=None if dq is None else np.array(dq, copy=True),
            dq2=None if dq2 is None else np.array(dq2, copy=True),
            var_poisson=None if var_poisson is None else np.array(var_poisson, dtype=np.float64, copy=True),
            var_rnoise=None if var_rnoise is None else np.array(var_rnoise, dtype=np.float64, copy=True),
            var_flat=None if var_flat is None else np.array(var_flat, dtype=np.float64, copy=True),
            units=units,
            units_note=(
                "Units come from the synthetic file. They are not Roman-calibrated units."
            ),
            wcs=wcs,
            meta=meta,
            declaration="SYNTHETIC_TEST",
            uncertainty_model=uncertainty_model,
        )
        return dataset
    finally:
        handle.close()


def _array_summary(handle: np.lib.npyio.NpzFile) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = {}
    for key in handle.files:
        array = np.asarray(handle[key])
        summary[key] = {"shape": list(array.shape), "dtype": str(array.dtype)}
    return summary
