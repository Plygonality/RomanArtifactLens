"""Choose a PSF adapter and return one evidence payload."""

from __future__ import annotations

import numpy as np

from romanartifactlens.cutouts.extract import Cutout
from romanartifactlens.errors import OptionalDependencyError
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.psf.gaussian_toy import fit_circular_gaussian
from romanartifactlens.psf.stpsf_adapter import compute_stpsf, stpsf_requirements
from romanartifactlens.settings import AnalysisSettings


def evaluate_psf(
    dataset: ImageDataset,
    cutout: Cutout,
    *,
    settings: AnalysisSettings,
    bad: np.ndarray,
) -> dict[str, object]:
    adapter = settings.psf_adapter
    if adapter == "none":
        return _not_evaluated(
            "MISSING_REFERENCE_PSF",
            "PSF comparison was not requested.",
            "No reference PSF was applied. A missing PSF comparison does not mean the candidate matches a Roman PSF.",
        )
    if adapter == "synthetic-gaussian":
        if dataset.dataset_kind != "SYNTHETIC_TEST":
            return _not_evaluated(
                "REFUSED_ON_NON_SYNTHETIC",
                "The synthetic Gaussian toy was refused because this dataset is not SYNTHETIC_TEST.",
                "A circular Gaussian is not a Roman PSF and is not fitted to Roman data.",
            )
        sigma = settings.psf_sigma_px if settings.psf_sigma_px is not None else 1.5
        local_x = cutout.candidate_x - cutout.origin_x
        local_y = cutout.candidate_y - cutout.origin_y
        fit = fit_circular_gaussian(
            cutout.science,
            cutout.coverage,
            bad,
            local_x,
            local_y,
            sigma,
        )
        fit["roman_calibrated"] = False
        fit["model_name"] = "synthetic_gaussian_toy"
        fit["interpretation"] = (
            "Residual from a circular Gaussian toy with a declared sigma. "
            "This is not an STPSF or CRDS Roman PSF. A shape difference does not establish "
            "an instrumental origin or an astrophysical novelty."
        )
        return fit
    if adapter == "stpsf":
        missing = stpsf_requirements(dataset.meta)
        if missing is not None:
            return _not_evaluated(
                "MISSING_REFERENCE_PSF",
                f"STPSF was not run because {missing}.",
                "Position and filter context are required before a Roman PSF model is meaningful. "
                "No Gaussian was substituted.",
            )
        fov = int(cutout.shape[0])
        try:
            image = compute_stpsf(
                optical_element=str(dataset.meta["optical_element"]),
                detector=str(dataset.meta["detector"]),
                x=cutout.candidate_x,
                y=cutout.candidate_y,
                fov_pixels=fov,
            )
        except OptionalDependencyError:
            raise
        except Exception as exc:
            return _not_evaluated(
                "STPSF_FAILED_CLOSED",
                f"STPSF did not return a model ({type(exc).__name__}: {exc}).",
                "The PSF check failed closed. No toy PSF was substituted and no residual is claimed.",
            )
        return _fit_supplied_psf(cutout, bad, image)
    return _not_evaluated("UNKNOWN_ADAPTER", f"Unknown PSF adapter {adapter}.", "No PSF was evaluated.")


def _fit_supplied_psf(cutout: Cutout, bad: np.ndarray, psf_image: np.ndarray) -> dict[str, object]:
    """Scale a supplied PSF stamp. The stamp is not renamed if its shape differs."""

    usable = cutout.coverage & ~bad & np.isfinite(cutout.science)
    stamp = np.asarray(psf_image, dtype=np.float64)
    if stamp.shape != cutout.science.shape:
        return _not_evaluated(
            "PSF_SHAPE_MISMATCH",
            f"STPSF stamp shape {stamp.shape} does not match the cutout {cutout.science.shape}.",
            "The stamp was not resampled by a silent interpolation.",
        )
    if int(np.count_nonzero(usable)) < 8 or not np.any(np.isfinite(stamp)):
        return _not_evaluated("TOO_FEW_PIXELS", "Too few valid pixels to scale the PSF.", "No residual was claimed.")
    stamp = np.nan_to_num(stamp, nan=0.0)
    design = np.column_stack([stamp[usable], np.ones(int(np.count_nonzero(usable)))])
    coeff, _residuals, _rank, _singular = np.linalg.lstsq(design, cutout.science[usable], rcond=None)
    amplitude = float(coeff[0])
    background = float(coeff[1])
    model = amplitude * stamp + background
    residual = cutout.science - model
    rss = float(np.sum(residual[usable] ** 2))
    return {
        "status": "MEASURED",
        "reason": "STPSF_SCALED",
        "amplitude": amplitude,
        "background": background,
        "dx_px": 0.0,
        "dy_px": 0.0,
        "rss": rss,
        "rmse": float(np.sqrt(rss / int(np.count_nonzero(usable)))),
        "n_pixels": int(np.count_nonzero(usable)),
        "model": model,
        "residual": residual,
        "roman_calibrated": False,
        "model_name": "stpsf.Roman",
        "interpretation": (
            "Amplitude and background were scaled to an STPSF Roman model at the stated detector "
            "position and filter. Normalization is a fit to this cutout, not a photometric calibration. "
            "A residual does not by itself decide instrument versus astrophysics."
        ),
    }


def _not_evaluated(reason: str, description: str, interpretation: str) -> dict[str, object]:
    return {
        "status": "NOT_EVALUATED",
        "reason": reason,
        "description": description,
        "interpretation": interpretation,
        "roman_calibrated": False,
        "model_name": None,
        "residual": None,
        "model": None,
    }
