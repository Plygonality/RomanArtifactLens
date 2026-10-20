"""Stable diagnostic codes and the text returned by ``explain-diagnostic``."""

from __future__ import annotations

EXPLANATIONS: dict[str, str] = {
    "RAL-DQ-001": (
        "Whether a per-pixel DQ array was present. Missing DQ is NOT_EVALUATED. "
        "It is not a clean bill of health. L3 mosaics normally have no DQ array; "
        "use the context map and the contributing L2 exposures, which v0.1 does not ingest."
    ),
    "RAL-DQ-010": (
        "Bitwise decomposition of the single central pixel. Flags are tested with bitwise AND, "
        "not equality. Combined bits, including DO_NOT_USE mixed with other flags, are all listed. "
        "Unknown bits stay UNKNOWN_DQ_BIT."
    ),
    "RAL-DQ-011": (
        "A named DQ flag has a non-zero count inside the circular aperture of pixel centers. "
        "The flag records a pipeline or reference-file condition. It does not classify the candidate."
    ),
    "RAL-DQ-012": (
        "Named flags in the background annulus. Annulus flags are context for the sky estimate. "
        "They are excluded from the sky under the selected DQ policy when they include DO_NOT_USE "
        "or, if requested, any non-zero bit."
    ),
    "RAL-DQ-020": (
        "Fraction of aperture pixel centers carrying DO_NOT_USE. The Roman handbook recommends "
        "excluding those pixels even when other bits are also set. Exclusion is a measurement policy, "
        "not a verdict that the candidate is artificial."
    ),
    "RAL-DQ-031": (
        "JUMP_DET overlaps the aperture. Ramp-fit jumps are associated with cosmic rays and with "
        "other discontinuities. The overlap does not prove this candidate is a cosmic ray."
    ),
    "RAL-DQ-032": (
        "SATURATED overlaps the aperture. Saturation can change apparent shape and brightness."
    ),
    "RAL-DQ-040": (
        "A bit in the DQ integer is not named by the flag dictionary in use. It is reported as "
        "UNKNOWN_DQ_BIT and is not given a guessed meaning."
    ),
    "RAL-DQ-060": (
        "L3 mosaic DQ semantics. Absence of L3 DQ is not treated as all pixels good, and an L3 "
        "array is not given L2 flag meanings by default."
    ),
    "RAL-DQ-070": (
        "The dq2 array, when present, is counted but not decoded. roman_datamodels pixel flag "
        "names are not applied to dq2."
    ),
    "RAL-PIX-001": "Non-finite science or error values inside the aperture.",
    "RAL-PIX-002": (
        "The aperture is truncated by the image edge, or the candidate is closer to the border "
        "than the aperture radius. Off-image pixel centers are counted and are not filled with zeros."
    ),
    "RAL-PIX-003": (
        "Error-array quality: missing, non-finite, non-positive, inconsistent with a complete "
        "variance budget, or unexpectedly small. No detection significance is quoted in those states."
    ),
    "RAL-PIX-010": (
        "Local background level and robust scale from the annulus, after the DQ policy mask. "
        "Too few valid pixels yields INSUFFICIENT_SAMPLES rather than a silent sky value."
    ),
    "RAL-PIX-012": (
        "Central excess divided by the supplied error at the central pixel, only when the error "
        "model is finite, positive, and not internally inconsistent. The ratio is not an artefact probability."
    ),
    "RAL-MORPH-001": (
        "Basic shape from a photutils segmentation of pixels above the local threshold: area, "
        "ellipticity, axis ratio, orientation. A shape is not an origin."
    ),
    "RAL-MORPH-010": (
        "Heuristic: one pixel dominates the local excess. This can be raised without a JUMP_DET flag. "
        "It is not a cosmic-ray classification."
    ),
    "RAL-PSF-020": (
        "PSF residual status. The default is NOT_EVALUATED. A synthetic Gaussian is labelled as a toy. "
        "STPSF is used only with filter and detector metadata and is not replaced by a Gaussian on failure."
    ),
    "RAL-CAT-010": (
        "External catalogue columns such as anomaly_score. NGRST-style anomaly scores are within-image "
        "rankings. This code records that they were not interpreted."
    ),
}

FLAG_CODES = {
    "JUMP_DET": "RAL-DQ-031",
    "SATURATED": "RAL-DQ-032",
    "HOT": "RAL-DQ-033",
    "DEAD": "RAL-DQ-034",
    "LOW_QE": "RAL-DQ-035",
    "PERSISTENCE": "RAL-DQ-036",
    "GW_AFFECTED_DATA": "RAL-DQ-037",
    "WARM": "RAL-DQ-038",
    "NONLINEAR": "RAL-DQ-039",
    "DROPOUT": "RAL-DQ-041",
    "AD_FLOOR": "RAL-DQ-042",
    "OUTLIER": "RAL-DQ-043",
    "TELEGRAPH": "RAL-DQ-044",
}


def explain(code: str) -> str | None:
    if code in EXPLANATIONS:
        return EXPLANATIONS[code]
    if code in FLAG_CODES.values():
        return EXPLANATIONS["RAL-DQ-011"]
    return None
