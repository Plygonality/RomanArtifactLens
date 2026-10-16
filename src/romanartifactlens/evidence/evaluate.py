"""Turn a cutout into a candidate evidence packet.

Observed flags stay in their own items. Heuristics stay in theirs. Nothing in
this module emits an artefact probability or a confirmed-real / confirmed-artefact
status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from romanartifactlens.catalogs.ingest import Candidate
from romanartifactlens.cutouts.extract import Cutout, extract_cutout
from romanartifactlens.cutouts.stretch import asinh_display
from romanartifactlens.dq.decode import decompose, summarize_region
from romanartifactlens.dq.definitions import FLAG_MEANINGS, FlagDictionary
from romanartifactlens.dq.regions import circular_region, nearest_pixel
from romanartifactlens.evidence.codes import FLAG_CODES
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.psf.evaluate import evaluate_psf
from romanartifactlens.settings import AnalysisSettings
from romanartifactlens.stats.background import estimate_background
from romanartifactlens.stats.morphology import measure_morphology
from romanartifactlens.stats.uncertainty import assess_uncertainty

NOT_CONCLUDED = (
    "This packet does not establish that the candidate is astrophysically real.",
    "This packet does not establish that the candidate is an instrumental artefact.",
    "A DQ flag records a pipeline or reference-file condition, not a complete physical origin.",
)


@dataclass
class CandidatePacket:
    report: dict[str, Any]
    cutout: Cutout
    display: np.ndarray
    display_limits: dict[str, Any]
    psf_residual: np.ndarray | None
    psf_model: np.ndarray | None


def evaluate_candidate(
    dataset: ImageDataset,
    candidate: Candidate,
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
) -> CandidatePacket:
    assert candidate.x is not None and candidate.y is not None
    ny, nx = dataset.shape
    aperture = circular_region(dataset.shape, candidate.x, candidate.y, settings.aperture_radius_px, 0.0)
    annulus = circular_region(
        dataset.shape,
        candidate.x,
        candidate.y,
        settings.annulus_outer(),
        settings.annulus_inner(),
    )
    cx, cy = nearest_pixel(candidate.x, candidate.y)
    central_on = 0 <= cy < ny and 0 <= cx < nx
    central = (cy, cx) if central_on else None
    edge_distance = min(candidate.x, candidate.y, (nx - 1) - candidate.x, (ny - 1) - candidate.y)
    stats_mask = _policy_mask(dataset, aperture.mask, settings, dictionary)
    annulus_stats = _policy_mask(dataset, annulus.mask, settings, dictionary)
    background = estimate_background(
        np.asarray(dataset.science[annulus_stats], dtype=np.float64),
        method=settings.background,
        sigma=settings.background_sigma,
        min_pixels=settings.min_background_pixels,
    )
    uncertainty = assess_uncertainty(
        science=dataset.science,
        err=dataset.err,
        var_poisson=dataset.var_poisson,
        var_rnoise=dataset.var_rnoise,
        var_flat=dataset.var_flat,
        aperture=aperture.mask,
        central=central,
        background=background["value"] if background["status"] == "MEASURED" else None,
        dataset_kind=dataset.dataset_kind,
        uncertainty_model=dataset.uncertainty_model,
    )
    cutout = extract_cutout(dataset, candidate.x, candidate.y, settings.aperture_radius_px)
    local_bad = _cutout_bad(cutout, dataset, settings, dictionary, settings.aperture_radius_px)
    morphology = measure_morphology(
        cutout.science,
        coverage=cutout.coverage,
        bad=local_bad,
        background=background["value"] if background["status"] == "MEASURED" else None,
        noise_scale=background["scale"] if background["status"] == "MEASURED" else None,
        nsigma=settings.morphology_nsigma,
        local_x=candidate.x - cutout.origin_x,
        local_y=candidate.y - cutout.origin_y,
    )
    psf = evaluate_psf(dataset, cutout, settings=settings, bad=local_bad)
    display, display_limits = asinh_display(cutout.science, cutout.coverage)
    dq_summary = _dq_summary(dataset, dictionary, aperture.mask, annulus.mask, central)
    evidence = _evidence(
        dataset=dataset,
        candidate=candidate,
        settings=settings,
        dictionary=dictionary,
        aperture=aperture,
        annulus=annulus,
        central=central,
        edge_distance=edge_distance,
        dq_summary=dq_summary,
        background=background,
        uncertainty=uncertainty,
        morphology=morphology,
        psf=psf,
        n_stats=int(np.count_nonzero(stats_mask)),
    )
    status = _overall(dataset, evidence, background, aperture.n_on_image, central_on)
    limitations = _limitations(dataset, psf, uncertainty)
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "candidate_id": candidate.candidate_id,
        "dataset_level": dataset.data_level,
        "dataset_kind": dataset.dataset_kind,
        "units": dataset.units,
        "units_note": dataset.units_note,
        "overall_review_status": status,
        "position": {
            "x": candidate.x,
            "y": candidate.y,
            "ra_deg": candidate.ra_deg,
            "dec_deg": candidate.dec_deg,
            "central_pixel": None if central is None else {"x": central[1], "y": central[0]},
            "on_image": bool(central_on and aperture.n_on_image > 0),
            "edge_distance_px": edge_distance,
            "coordinate_convention": (
                "0-based pixel centers; x is the column index and y is the row index; "
                "science[y, x] is the central sample when x and y are integers. "
                "NumPy round-half-to-even selects the central pixel."
            ),
        },
        "catalogue_metadata": candidate.catalogue_metadata,
        "cutout": {
            "radius_px": settings.aperture_radius_px,
            "shape": list(cutout.shape),
            "origin_xy": [cutout.origin_x, cutout.origin_y],
            "n_coverage": int(np.count_nonzero(cutout.coverage)),
            "padded_with_nan": bool(np.any(~cutout.coverage)),
        },
        "dq_summary": dq_summary,
        "measurements": {
            "background": background,
            "uncertainty": {key: value for key, value in uncertainty.items()},
            "morphology": morphology,
            "n_aperture_pixels_on_image": aperture.n_on_image,
            "n_aperture_pixels_off_image": aperture.n_off_image,
            "n_annulus_pixels_on_image": annulus.n_on_image,
            "n_annulus_valid_for_stats": int(np.count_nonzero(annulus_stats)),
            "n_aperture_valid_for_stats": int(np.count_nonzero(stats_mask)),
        },
        "evidence": evidence,
        "limitations": limitations,
        "not_concluded": list(NOT_CONCLUDED),
        "analysis_settings": settings.to_dict(),
    }
    return CandidatePacket(
        report=report,
        cutout=cutout,
        display=display,
        display_limits=display_limits,
        psf_residual=psf.get("residual") if isinstance(psf.get("residual"), np.ndarray) else None,
        psf_model=psf.get("model") if isinstance(psf.get("model"), np.ndarray) else None,
    )


def _evidence(
    *,
    dataset: ImageDataset,
    candidate: Candidate,
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
    aperture: Any,
    annulus: Any,
    central: tuple[int, int] | None,
    edge_distance: float,
    dq_summary: dict[str, Any],
    background: dict[str, Any],
    uncertainty: dict[str, Any],
    morphology: dict[str, Any],
    psf: dict[str, Any],
    n_stats: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    level_is_l3 = dataset.data_level.upper() == "L3" or dataset.dataset_kind == "ROMAN_L3"
    if dataset.dq is None:
        items.append(
            _item(
                "RAL-DQ-001",
                "NOT_EVALUATED",
                "MISSING_DQ",
                "No per-pixel DQ array was available.",
                "Absence of DQ is not a statement that the pixels are good.",
                "dq",
                None,
                "DQ required for flag evidence",
                "NOT_APPLICABLE",
            )
        )
    else:
        items.append(
            _item(
                "RAL-DQ-001",
                "OBSERVED_FLAG",
                "PRESENT",
                "A per-pixel DQ array was read and decoded with bitwise tests.",
                "Flag names come from the dictionary recorded in the manifest. "
                "A clear pixel is not evidence of astrophysical reality.",
                "dq",
                int(dataset.dq.size),
                "bitwise AND against the flag dictionary",
                "DIRECT",
            )
        )
    if level_is_l3:
        items.append(
            _item(
                "RAL-DQ-060",
                "NOT_EVALUATED",
                "L3_DQ_SEMANTICS",
                "This dataset is L3. L3 mosaics do not normally carry per-pixel DQ, and L2 flag "
                "meanings are not copied onto an L3 array.",
                "A context map and the contributing L2 exposures would be required. v0.1 does not "
                "perform that join. An empty or missing L3 DQ state is not reported as clean.",
                "data_level",
                dataset.data_level,
                "L3 is not treated as L2",
                "NOT_APPLICABLE",
            )
        )
    central_decode = dq_summary.get("central")
    if isinstance(central_decode, dict):
        flags = list(central_decode.get("flags") or [])
        unknown = list(central_decode.get("unknown_bits") or [])
        items.append(
            _item(
                "RAL-DQ-010",
                "OBSERVED_FLAG",
                "PRESENT" if flags or unknown else "ABSENT",
                "Central pixel DQ decomposes to "
                + (", ".join(flags) if flags else "no named flags")
                + (f"; unknown bits {unknown}" if unknown else ""),
                "No named flag on the central pixel is not evidence that the candidate is real "
                "or free of unflagged artefacts."
                if not flags and not unknown
                else "Every set bit is listed. Combined flags are not collapsed to one integer label.",
                "dq[central]",
                central_decode.get("raw"),
                "bitwise decomposition",
                "DIRECT",
                components=central_decode.get("components"),
            )
        )
    aperture_summary = dq_summary.get("aperture") or {}
    if dataset.dq is not None:
        counts = dict(aperture_summary.get("flag_counts") or {})
        fractions = dict(aperture_summary.get("flag_fractions") or {})
        dnu = aperture_summary.get("do_not_use_fraction")
        items.append(
            _item(
                "RAL-DQ-020",
                "OBSERVED_FLAG",
                "PRESENT" if counts.get("DO_NOT_USE", 0) else "ABSENT",
                "DO_NOT_USE fraction inside the aperture.",
                "Pixels with DO_NOT_USE are left out of the default statistics, including when other "
                "bits are set. The fraction is not an artefact probability.",
                "dq aperture",
                dnu,
                "exclude DO_NOT_USE from statistics when policy is exclude_do_not_use",
                "DIRECT",
                count=counts.get("DO_NOT_USE", 0),
                n_pixels=aperture_summary.get("n_pixels"),
            )
        )
        for name, count in counts.items():
            if name == "DO_NOT_USE":
                continue
            code = FLAG_CODES.get(name, "RAL-DQ-011")
            items.append(
                _item(
                    code,
                    "OBSERVED_FLAG",
                    "PRESENT",
                    f"Candidate aperture overlaps pixels flagged {name}.",
                    FLAG_MEANINGS.get(name, "Named DQ flag in the aperture."),
                    "dq aperture",
                    fractions.get(name),
                    "fraction of on-image aperture pixel centers",
                    "DIRECT",
                    flag=name,
                    count=count,
                    n_pixels=aperture_summary.get("n_pixels"),
                    policy=dictionary.by_name()[name].policy if name in dictionary.by_name() else "UNLISTED",
                )
            )
        unknown_counts = dict(aperture_summary.get("unknown_bit_counts") or {})
        if unknown_counts:
            items.append(
                _item(
                    "RAL-DQ-040",
                    "OBSERVED_FLAG",
                    "PRESENT",
                    "The aperture contains DQ bits that are not in the flag dictionary.",
                    "Unknown bits are reported as UNKNOWN_DQ_BIT and are not assigned a fabricated cause.",
                    "dq aperture",
                    unknown_counts,
                    "bits outside the installed or snapshot dictionary",
                    "DIRECT",
                )
            )
        else:
            items.append(
                _item(
                    "RAL-DQ-040",
                    "OBSERVED_FLAG",
                    "ABSENT",
                    "No unknown DQ bits were set in the aperture.",
                    "This check uses the dictionary provenance in the manifest. It does not add names for reserved bits.",
                    "dq aperture",
                    {},
                    "unknown bits remain visible",
                    "DIRECT",
                )
            )
        annulus_counts = dict((dq_summary.get("annulus") or {}).get("flag_counts") or {})
        items.append(
            _item(
                "RAL-DQ-012",
                "OBSERVED_FLAG",
                "PRESENT" if annulus_counts else "ABSENT",
                "Annulus flag counts: " + (", ".join(f"{key}={value}" for key, value in annulus_counts.items()) or "none"),
                "Annulus flags inform the background mask. They are not by themselves a claim about the candidate's origin.",
                "dq annulus",
                annulus_counts,
                settings.dq_policy,
                "DIRECT",
            )
        )
    if dataset.dq2 is not None and central is not None:
        n_dq2 = int(np.count_nonzero(np.asarray(dataset.dq2)[aperture.mask])) if aperture.n_on_image else 0
        items.append(
            _item(
                "RAL-DQ-070",
                "UNAVAILABLE",
                "PRESENT" if n_dq2 else "ABSENT",
                "dq2 is present. Pixel-flag names are not applied to it.",
                "Non-zero dq2 values are counted only. They are not decoded as DO_NOT_USE or JUMP_DET.",
                "dq2",
                n_dq2,
                "no dq2 dictionary",
                "NOT_APPLICABLE",
            )
        )
    if aperture.n_on_image:
        aperture_science = dataset.science[aperture.mask]
        n_bad_science = int(np.count_nonzero(~np.isfinite(aperture_science)))
    else:
        n_bad_science = 0
    items.append(
        _item(
            "RAL-PIX-001",
            "DERIVED_METRIC",
            "PRESENT" if n_bad_science else "ABSENT",
            f"{n_bad_science} aperture pixels have non-finite science values.",
            "Non-finite samples are excluded from statistics and are not replaced with zeros.",
            "science aperture",
            n_bad_science,
            "finite science required",
            "DIRECT",
        )
    )
    off_fraction = aperture.off_image_fraction
    truncated = bool(off_fraction and off_fraction > 0) or edge_distance < settings.aperture_radius_px
    items.append(
        _item(
            "RAL-PIX-002",
            "DERIVED_METRIC",
            "PRESENT" if truncated else "ABSENT",
            "Aperture coverage relative to the image boundary.",
            "Off-image pixel centers are counted in n_off_image and omitted from fractions. "
            "They are not treated as good pixels.",
            "aperture geometry",
            off_fraction,
            "pixel centers inside the radius",
            "DIRECT",
            n_on_image=aperture.n_on_image,
            n_off_image=aperture.n_off_image,
            edge_distance_px=edge_distance,
        )
    )
    items.append(
        _item(
            "RAL-PIX-003",
            "DERIVED_METRIC" if uncertainty["status"] == "MEASURED" else "NOT_EVALUATED",
            str(uncertainty["status"]),
            f"Uncertainty check: {uncertainty['reason']}.",
            str(uncertainty.get("assumption") or "No significance is quoted unless the error values support it."),
            "err",
            uncertainty.get("central_err"),
            "finite, positive, and not inconsistent with a complete variance budget",
            "DIRECT" if uncertainty["status"] == "MEASURED" else "NOT_APPLICABLE",
            reason=uncertainty["reason"],
        )
    )
    items.append(
        _item(
            "RAL-PIX-010",
            "DERIVED_METRIC",
            str(background["status"]),
            "Local annulus background.",
            "The sky estimate uses unmasked annulus pixels only. It is not a source flux.",
            "science annulus",
            background.get("value"),
            f"at least {settings.min_background_pixels} valid pixels; estimator {settings.background}",
            "DIRECT" if background["status"] == "MEASURED" else "NOT_APPLICABLE",
            scale=background.get("scale"),
            n_used=background.get("n_used"),
            n_valid=background.get("n_valid"),
        )
    )
    if uncertainty["status"] == "MEASURED":
        items.append(
            _item(
                "RAL-PIX-012",
                "DERIVED_METRIC",
                "MEASURED",
                "Central excess divided by the supplied central error.",
                str(uncertainty["assumption"]),
                "science and err at central pixel",
                uncertainty.get("significance"),
                "quoted only with a finite positive error and a measured background",
                "DIRECT",
                method=uncertainty.get("method"),
            )
        )
    else:
        items.append(
            _item(
                "RAL-PIX-012",
                "NOT_EVALUATED",
                str(uncertainty["status"]),
                "A significance ratio was not quoted.",
                "Missing, non-finite, non-positive, or inconsistent errors do not produce a sigma. "
                "This is not a non-detection claim.",
                "err",
                None,
                uncertainty["reason"],
                "NOT_APPLICABLE",
            )
        )
    items.append(
        _item(
            "RAL-MORPH-001",
            "DERIVED_METRIC",
            str(morphology["status"]),
            "Local segmentation shape summary.",
            "Area, axis ratio, and concentration describe the pixels above threshold. "
            "They do not establish an instrumental or astrophysical origin.",
            "science cutout",
            morphology.get("area_px"),
            f"threshold = background + {settings.morphology_nsigma} * robust scale",
            "DIRECT" if morphology["status"] == "MEASURED" else "NOT_APPLICABLE",
            ellipticity=morphology.get("ellipticity"),
            axis_ratio=morphology.get("axis_ratio"),
            orientation_rad=morphology.get("orientation_rad"),
            central_concentration=morphology.get("central_concentration"),
            method=morphology.get("method"),
            reason=morphology.get("reason"),
        )
    )
    jump_present = bool((dq_summary.get("aperture") or {}).get("flag_counts", {}).get("JUMP_DET", 0))
    if morphology.get("isolated_pixel"):
        interpretation = (
            "A single pixel dominates the local excess. This is a morphology heuristic. "
            "It is not a cosmic-ray classification."
        )
        if jump_present:
            interpretation += " JUMP_DET is reported separately as an observed flag and is not proof either."
        else:
            interpretation += " No JUMP_DET bit was set in the aperture, so this warning is not jump-flag evidence."
        items.append(
            _item(
                "RAL-MORPH-010",
                "HEURISTIC_WARNING",
                "PRESENT",
                "Isolated-pixel morphology heuristic.",
                interpretation,
                "segmentation area",
                morphology.get("area_px"),
                "area == 1 or a single pixel above threshold holding most of the positive excess",
                "HEURISTIC",
            )
        )
    elif morphology["status"] == "MEASURED":
        items.append(
            _item(
                "RAL-MORPH-010",
                "HEURISTIC_WARNING",
                "ABSENT",
                "The isolated-pixel heuristic did not trigger.",
                "Absence of this heuristic is not a cosmic-ray rejection and not a confirmation of a real source.",
                "segmentation area",
                morphology.get("area_px"),
                "single-pixel dominance",
                "HEURISTIC",
            )
        )
    psf_status = str(psf.get("status"))
    psf_kind = "SIMULATED_EXPECTATION" if psf.get("model_name") == "synthetic_gaussian_toy" else (
        "DERIVED_METRIC" if psf_status == "MEASURED" else "NOT_EVALUATED"
    )
    items.append(
        _item(
            "RAL-PSF-020",
            psf_kind,
            "MISSING_REFERENCE_PSF" if psf.get("reason") == "MISSING_REFERENCE_PSF" else psf_status,
            str(psf.get("description") or psf.get("reason") or "PSF comparison"),
            str(
                psf.get("interpretation")
                or "PSF comparison was not evaluated. No Roman PSF residual is claimed."
            ),
            "psf adapter " + settings.psf_adapter,
            psf.get("rmse"),
            "reference model required; Gaussian toy is not a Roman PSF",
            "NOT_APPLICABLE" if psf_status != "MEASURED" else "HEURISTIC",
            model_name=psf.get("model_name"),
            roman_calibrated=False,
            amplitude=psf.get("amplitude"),
            dx_px=psf.get("dx_px"),
            dy_px=psf.get("dy_px"),
            sigma_px=psf.get("sigma_px"),
            reason=psf.get("reason"),
        )
    )
    if "anomaly_score" in candidate.catalogue_metadata:
        items.append(
            _item(
                "RAL-CAT-010",
                "UNAVAILABLE",
                "NOT_INTERPRETED",
                "The catalogue supplied anomaly_score. It was stored as metadata and not interpreted.",
                "NGRST-style anomaly scores are within-image rankings, not detection significances "
                "and not artefact probabilities. The live toolkit schema was not verified.",
                "catalogue anomaly_score",
                candidate.catalogue_metadata.get("anomaly_score"),
                "do not treat as a probability",
                "NOT_APPLICABLE",
            )
        )
    items.append(
        _item(
            "RAL-PIX-004",
            "DERIVED_METRIC",
            "MEASURED",
            "Count of aperture pixels accepted by the DQ and finite-value policy.",
            "This count is the sample available for local statistics after the stated mask.",
            "policy mask",
            n_stats,
            settings.dq_policy,
            "DIRECT",
        )
    )
    return items


def _overall(
    dataset: ImageDataset,
    evidence: list[dict[str, Any]],
    background: dict[str, Any],
    n_on_image: int,
    central_on: bool,
) -> str:
    if n_on_image == 0 or not central_on:
        return "INSUFFICIENT_EVIDENCE"
    review = False
    for item in evidence:
        code = item["code"]
        status = item["status"]
        kind = item["kind"]
        if status not in {"PRESENT", "INVALID", "INSUFFICIENT_SAMPLES"}:
            continue
        if code in {"RAL-DQ-020", "RAL-DQ-031", "RAL-DQ-032", "RAL-DQ-033", "RAL-DQ-034", "RAL-DQ-035"} and status == "PRESENT":
            review = True
        if code == "RAL-DQ-011" and status == "PRESENT":
            review = True
        if code in FLAG_CODES.values() and status == "PRESENT":
            review = True
        if code == "RAL-DQ-040" and status == "PRESENT":
            review = True
        if code == "RAL-DQ-010" and status == "PRESENT":
            review = True
        if code in {"RAL-PIX-001", "RAL-PIX-002"} and status == "PRESENT":
            review = True
        if code == "RAL-PIX-003" and status == "INVALID":
            review = True
        if code == "RAL-MORPH-010" and kind == "HEURISTIC_WARNING" and status == "PRESENT":
            review = True
    if review:
        return "REVIEW_RECOMMENDED"
    if dataset.dq is None or dataset.data_level.upper() == "L3" or dataset.dataset_kind == "ROMAN_L3":
        return "INSUFFICIENT_EVIDENCE"
    if background.get("status") != "MEASURED":
        return "INSUFFICIENT_EVIDENCE"
    return "NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS"


def _limitations(dataset: ImageDataset, psf: dict[str, Any], uncertainty: dict[str, Any]) -> list[str]:
    notes = [
        "RomanArtifactLens is a diagnostic assistant. It does not classify candidates as alien, novel, extragalactic, cosmic-ray, instrumental, or not real.",
        "Multi-exposure persistence, filter-to-filter, and transient comparisons are NOT_EVALUATED in v0.1. Raw detector indices are not treated as co-registered.",
        "L3 context-to-L2 contributor inspection is NOT_EVALUATED unless a later version is given both the context map and the L2 products.",
    ]
    if dataset.dataset_kind == "SYNTHETIC_TEST":
        notes.append(
            "SYNTHETIC_TEST: this image was generated inside RomanArtifactLens. "
            "It is not a Roman-calibrated exposure and it does not use a Roman observation identifier."
        )
    if dataset.units is None:
        notes.append(dataset.units_note or "Science units were not attached to the array.")
    if psf.get("status") != "MEASURED":
        notes.append("PSF comparison: NOT_EVALUATED. No Roman PSF residual is shown.")
    elif psf.get("model_name") == "synthetic_gaussian_toy":
        notes.append("The PSF panel is a synthetic Gaussian toy, not a Roman PSF.")
    if uncertainty.get("status") != "MEASURED":
        notes.append(
            f"Significance was not quoted ({uncertainty.get('reason')}). That is an evidence gap, not a non-detection."
        )
    notes.append(dataset.meta.get("validation_note", ""))
    return [note for note in notes if note]


def _dq_summary(
    dataset: ImageDataset,
    dictionary: FlagDictionary,
    aperture_mask: np.ndarray,
    annulus_mask: np.ndarray,
    central: tuple[int, int] | None,
) -> dict[str, Any]:
    if dataset.dq is None:
        return {"available": False, "central": None, "aperture": None, "annulus": None}
    central_decode = None
    if central is not None:
        row, col = central
        central_decode = decompose(int(dataset.dq[row, col]), dictionary).to_dict()
    return {
        "available": True,
        "central": central_decode,
        "aperture": summarize_region(dataset.dq, aperture_mask, dictionary),
        "annulus": summarize_region(dataset.dq, annulus_mask, dictionary),
    }


def _policy_mask(
    dataset: ImageDataset,
    region: np.ndarray,
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
) -> np.ndarray:
    mask = region & np.isfinite(dataset.science)
    if dataset.err is not None:
        mask = mask & np.isfinite(dataset.err)
    if dataset.dq is None or settings.dq_policy == "include_all":
        return mask
    dq = np.asarray(dataset.dq)
    if settings.dq_policy == "exclude_nonzero":
        return mask & (dq == 0)
    do_not_use = dictionary.by_name().get("DO_NOT_USE")
    bit = 1 if do_not_use is None else do_not_use.value
    return mask & ((dq & np.uint32(bit)) == 0)


def _cutout_bad(
    cutout: Cutout,
    dataset: ImageDataset,
    settings: AnalysisSettings,
    dictionary: FlagDictionary,
    radius: float,
) -> np.ndarray:
    yy, xx = np.indices(cutout.shape)
    x = cutout.origin_x + xx
    y = cutout.origin_y + yy
    outside = np.hypot(x - cutout.candidate_x, y - cutout.candidate_y) > radius
    bad = outside | ~cutout.coverage | ~np.isfinite(cutout.science)
    if cutout.dq is None or settings.dq_policy == "include_all":
        return bad
    if settings.dq_policy == "exclude_nonzero":
        return bad | (cutout.dq != 0)
    do_not_use = dictionary.by_name().get("DO_NOT_USE")
    bit = 1 if do_not_use is None else do_not_use.value
    return bad | ((cutout.dq & np.uint32(bit)) != 0)


def _item(
    code: str,
    kind: str,
    status: str,
    description: str,
    interpretation: str,
    source_field: str,
    value: object,
    threshold_or_policy: str,
    confidence_class: str,
    **context: object,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "kind": kind,
        "status": status,
        "description": description,
        "interpretation": interpretation,
        "source_field": source_field,
        "value": value,
        "threshold_or_policy": threshold_or_policy,
        "confidence_class": confidence_class,
        "context": context,
    }
    return payload
