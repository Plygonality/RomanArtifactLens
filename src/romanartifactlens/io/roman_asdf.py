"""Roman ASDF reader.

Only ``roman_datamodels`` datamodels are accepted. A generic ASDF tree is not
treated as an image. L1 ramps are rejected. L3 mosaics are opened only so the
report can say that per-pixel L2 DQ is absent; they are not relabelled as L2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from romanartifactlens.errors import (
    InvalidDataError,
    OptionalDependencyError,
    UnsupportedDatamodelError,
)
from romanartifactlens.io.dataset import ImageDataset

_L1_TYPES = {"RampModel", "ScienceRawModel", "RampFitOutputModel", "GuidewindowModel"}
_SCHEMA_UNITS = ("DN / s", "MJy / sr")


def read_roman_asdf(path: Path, asserted_level: str | None = None) -> ImageDataset:
    if not path.is_file():
        raise InvalidDataError(f"image file does not exist: {path}")
    try:
        import roman_datamodels as rdm
    except ImportError as exc:
        raise OptionalDependencyError(
            "Opening ASDF requires the roman extra: pip install 'romanartifactlens[roman]'. "
            "Generic ASDF loading is not a substitute."
        ) from exc

    try:
        model = rdm.open(path, memmap=True)
    except Exception as exc:
        message = str(exc)
        if "not a roman file" in message.lower() or "unknown datamodel" in message.lower():
            raise UnsupportedDatamodelError(
                f"{path.name} is not a supported Roman datamodel ({message}). "
                "v0.1 does not read generic ASDF science arrays."
            ) from exc
        raise UnsupportedDatamodelError(
            f"roman_datamodels could not open {path.name} as a supported datamodel: {message}"
        ) from exc

    model_name = type(model).__name__
    if model_name in _L1_TYPES:
        _close(model)
        raise UnsupportedDatamodelError(
            f"{model_name} is not an L2 calibrated image. v0.1 does not analyse ramps or "
            "guide-window products."
        )
    if model_name == "ImageModel":
        detected = "L2"
        kind = "ROMAN_L2"
    elif model_name == "MosaicModel":
        detected = "L3"
        kind = "ROMAN_L3"
    else:
        _close(model)
        raise UnsupportedDatamodelError(
            f"Datamodel {model_name} is not supported in v0.1. Supported types are "
            "ImageModel (L2) and, for an explicit not-evaluated DQ report, MosaicModel (L3)."
        )
    if asserted_level is not None and asserted_level.upper() != detected:
        _close(model)
        raise UnsupportedDatamodelError(
            f"Requested data level {asserted_level} but {path.name} opened as {model_name} "
            f"({detected}). The file was not reinterpreted."
        )

    science = _array(model, "data")
    if science is None or science.ndim != 2:
        _close(model)
        raise UnsupportedDatamodelError(
            f"{model_name} has no 2-D data array. v0.1 will not guess which extension is the image."
        )
    err = _array(model, "err")
    dq = _array(model, "dq")
    dq2 = _array(model, "dq2")
    var_poisson = _array(model, "var_poisson")
    var_rnoise = _array(model, "var_rnoise")
    var_flat = _array(model, "var_flat")
    for name, array in (
        ("err", err),
        ("dq", dq),
        ("dq2", dq2),
        ("var_poisson", var_poisson),
        ("var_rnoise", var_rnoise),
        ("var_flat", var_flat),
    ):
        if array is not None and array.shape != science.shape:
            _close(model)
            raise InvalidDataError(
                f"{name} shape {array.shape} does not match data shape {science.shape}"
            )
    if dq is not None and not np.issubdtype(dq.dtype, np.integer):
        _close(model)
        raise InvalidDataError("Roman dq array is not an integer bitmask")

    meta = _meta_summary(model, package_version=_version())
    meta["roman_validation"] = "opened_with_roman_datamodels"
    meta["observatory_product"] = False
    meta["validation_note"] = (
        "Opening an ImageModel or MosaicModel validates the reader interface only to the "
        "extent of the file that was supplied. A library fake or a simulation is not flight data."
    )
    wcs = None
    try:
        wcs = model.meta["wcs"]
    except Exception:
        wcs = None
    if wcs is not None and not hasattr(wcs, "pixel_to_world"):
        wcs = None

    units_note = (
        "roman_datamodels  ImageModel schema allows science units 'DN / s' or 'MJy / sr'. "
        "The ndarray did not carry a single attached unit, so neither value is applied. "
        "L2 handbook text describes calibrated rate images as DN/s; L3 mosaics as MJy/sr. "
        "Those handbook statements are context, not a measurement of this file."
        if _attached_unit(model, "data") is None
        else "Unit string was read from the data array."
    )
    dataset = ImageDataset(
        path=path,
        dataset_kind=kind,
        data_level=detected,
        science=science,
        err=err,
        dq=None if dq is None else _as_uint32_view(dq),
        dq2=None if dq2 is None else _as_uint32_view(dq2),
        var_poisson=var_poisson,
        var_rnoise=var_rnoise,
        var_flat=var_flat,
        units=_attached_unit(model, "data"),
        units_note=" ".join(units_note.split()),
        wcs=wcs,
        meta=meta,
        declaration=None,
        uncertainty_model="roman_l2_err_array" if detected == "L2" and err is not None else None,
        _closer=lambda: _close(model),
    )
    return dataset


def _as_uint32_view(array: np.ndarray) -> np.ndarray:
    if array.dtype == np.uint32:
        return array
    return np.asarray(array, dtype=np.uint32)


def _array(model: Any, key: str) -> np.ndarray | None:
    if key not in list(model.keys()):
        return None
    value = model[key]
    if value is None:
        return None
    # View when the datamodel already holds an ndarray. Do not astype here;
    # a dtype cast would copy a full detector plane.
    return np.asarray(value)


def _attached_unit(model: Any, key: str) -> str | None:
    if key not in list(model.keys()):
        return None
    value = model[key]
    unit = getattr(value, "unit", None)
    if unit is None:
        return None
    text = str(unit).strip()
    if text in {"", "None", "?"}:
        return None
    return text


def _close(model: Any) -> None:
    closer = getattr(model, "close", None)
    if callable(closer):
        closer()


def _version() -> str | None:
    try:
        from importlib.metadata import version

        return version("roman_datamodels")
    except Exception:
        return None


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not np.isfinite(value):
            return None
        if isinstance(value, str) and value.strip() in {"?", ""}:
            return None
        return value
    text = str(value).strip()
    if text in {"?", "None", ""}:
        return None
    return text


def _meta_summary(model: Any, package_version: str | None) -> dict[str, Any]:
    meta = model.meta
    instrument = meta["instrument"] if "instrument" in meta else {}
    exposure = meta["exposure"] if "exposure" in meta else {}
    observation = meta["observation"] if "observation" in meta else {}
    summary: dict[str, Any] = {
        "format": "roman_datamodels",
        "model_type": type(model).__name__,
        "roman_datamodels_version": package_version,
        "schema_allowed_science_units": list(_SCHEMA_UNITS),
        "telescope": _plain(meta["telescope"]) if "telescope" in meta else None,
        "origin": _plain(meta["origin"]) if "origin" in meta else None,
        "filename": _plain(meta["filename"]) if "filename" in meta else None,
        "calibration_software_name": _plain(meta["calibration_software_name"])
        if "calibration_software_name" in meta
        else None,
        "calibration_software_version": _plain(meta["calibration_software_version"])
        if "calibration_software_version" in meta
        else None,
        "detector": _plain(instrument["detector"]) if "detector" in instrument else None,
        "optical_element": _plain(instrument["optical_element"])
        if "optical_element" in instrument
        else None,
        "instrument": _plain(instrument["name"]) if "name" in instrument else None,
        "exposure_type": _plain(exposure["type"]) if "type" in exposure else None,
        "observation_id": _plain(observation["observation_id"])
        if "observation_id" in observation
        else None,
        "arrays": {},
    }
    analysed = {"data", "err", "dq", "dq2", "var_poisson", "var_rnoise", "var_flat"}
    arrays: dict[str, dict[str, object]] = {}
    for key in list(model.keys()):
        if key == "meta":
            continue
        value = model[key]
        if value is None:
            arrays[key] = {"present": False}
            continue
        # Read shape and dtype only. np.asarray would materialise reference-pixel
        # cubes that this tool does not analyse.
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        arrays[key] = {
            "present": True,
            "shape": None if shape is None else [int(axis) for axis in shape],
            "dtype": None if dtype is None else str(dtype),
            "analysed_as_image_plane": key in analysed,
        }
    summary["arrays"] = arrays
    return summary
