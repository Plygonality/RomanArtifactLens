"""Decide whether a central excess / error ratio may be quoted."""

from __future__ import annotations

import numpy as np


def assess_uncertainty(
    *,
    science: np.ndarray,
    err: np.ndarray | None,
    var_poisson: np.ndarray | None,
    var_rnoise: np.ndarray | None,
    var_flat: np.ndarray | None,
    aperture: np.ndarray,
    central: tuple[int, int] | None,
    background: float | None,
    dataset_kind: str,
    uncertainty_model: str | None,
) -> dict[str, object]:
    """Return a status for the central ratio. Invalid inputs do not produce a sigma."""

    base = {
        "status": "NOT_EVALUATED",
        "reason": "MISSING_ERROR_MAP",
        "central_err": None,
        "central_science": None,
        "significance": None,
        "method": None,
        "assumption": None,
        "inconsistent": False,
        "unexpectedly_small": False,
    }
    if central is None:
        base["reason"] = "CENTRAL_PIXEL_OFF_IMAGE"
        return base
    row, col = central
    if not (0 <= row < science.shape[0] and 0 <= col < science.shape[1]):
        base["reason"] = "CENTRAL_PIXEL_OFF_IMAGE"
        return base
    central_science = float(science[row, col])
    base["central_science"] = central_science if np.isfinite(central_science) else None
    if err is None:
        return base
    central_err = float(err[row, col])
    base["central_err"] = central_err if np.isfinite(central_err) else None
    aperture_err = np.asarray(err)[aperture]
    if not np.isfinite(central_science):
        base["status"] = "INVALID"
        base["reason"] = "NONFINITE_SCIENCE"
        return base
    if not np.isfinite(central_err):
        base["status"] = "INVALID"
        base["reason"] = "NONFINITE_ERROR"
        return base
    if central_err <= 0:
        base["status"] = "INVALID"
        base["reason"] = "NONPOSITIVE_ERROR"
        return base
    reference = _reference_variance(var_poisson, var_rnoise, var_flat, aperture)
    if reference is not None:
        ref_values, ref_complete = reference
        err_values = aperture_err[np.isfinite(aperture_err) & (aperture_err > 0)]
        aligned = _aligned_positive(aperture_err, ref_values)
        if aligned is not None:
            err2, ref = aligned
            if np.median(ref) > 0 and np.median(err_values) < 0.01 * np.median(np.sqrt(ref)):
                base["status"] = "INVALID"
                base["reason"] = "UNEXPECTEDLY_SMALL_ERROR"
                base["unexpectedly_small"] = True
                return base
            if ref_complete:
                relative = np.abs(err2 - ref) / np.maximum(ref, 1e-30)
                if float(np.median(relative)) > 0.25:
                    base["status"] = "INVALID"
                    base["reason"] = "INCONSISTENT_VARIANCE"
                    base["inconsistent"] = True
                    base["assumption"] = (
                        "err^2 disagrees with var_poisson + var_rnoise + var_flat by more than 25%. "
                        "No significance is quoted."
                    )
                    return base
    scale = max(abs(central_science), 1.0)
    if central_err < 1e-6 * scale:
        base["status"] = "INVALID"
        base["reason"] = "UNEXPECTEDLY_SMALL_ERROR"
        base["unexpectedly_small"] = True
        return base
    if background is None or not np.isfinite(background):
        base["status"] = "NOT_EVALUATED"
        base["reason"] = "BACKGROUND_UNAVAILABLE"
        base["central_err"] = central_err
        return base
    assumption = _assumption(dataset_kind, uncertainty_model, var_flat is not None)
    ratio = (central_science - background) / central_err
    base.update(
        {
            "status": "MEASURED",
            "reason": "QUOTED_UNDER_STATED_ASSUMPTION",
            "central_err": central_err,
            "significance": float(ratio),
            "method": "central_excess_over_supplied_err",
            "assumption": assumption,
        }
    )
    return base


def _reference_variance(
    var_poisson: np.ndarray | None,
    var_rnoise: np.ndarray | None,
    var_flat: np.ndarray | None,
    aperture: np.ndarray,
) -> tuple[np.ndarray, bool] | None:
    parts = [array for array in (var_poisson, var_rnoise, var_flat) if array is not None]
    if not parts:
        return None
    # Sum only the aperture samples. A full-frame float64 copy is not required.
    total = np.asarray(parts[0][aperture], dtype=np.float64)
    for array in parts[1:]:
        total = total + np.asarray(array[aperture], dtype=np.float64)
    complete = var_poisson is not None and var_rnoise is not None and var_flat is not None
    return total, complete


def _aligned_positive(err: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    err = np.asarray(err, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    ok = np.isfinite(err) & (err > 0) & np.isfinite(reference) & (reference > 0)
    if int(np.count_nonzero(ok)) < 5:
        return None
    return err[ok] ** 2, reference[ok]


def _assumption(dataset_kind: str, uncertainty_model: str | None, flat_present: bool) -> str:
    if dataset_kind == "ROMAN_L2":
        text = (
            "Ratio of central excess to the L2 err array at the central pixel. "
            "The Roman handbook describes L2 err as the pipeline total error, including a flat-field term. "
            "This ratio is not a source-detection significance and not an artefact probability."
        )
        if not flat_present:
            text += (
                " var_flat was not present, so err^2 was not required to equal var_poisson + var_rnoise."
            )
        return text
    model = uncertainty_model or "unspecified synthetic error array"
    return (
        f"Ratio of central excess to the supplied error under uncertainty_model={model}. "
        "This is not a Roman calibrated variance and not an artefact probability."
    )
