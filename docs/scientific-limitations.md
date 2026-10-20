# Scientific limitations

RomanArtifactLens answers a narrow question: which available measurements argue that instrument behaviour, processing, or local image quality could have shaped this detection, and which measurements are missing?

It does not answer whether the detection is astrophysical.

## Status language

Allowed overall statuses are `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS`, `REVIEW_RECOMMENDED`, and `INSUFFICIENT_EVIDENCE`.

`NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS` means the checks that had inputs did not fire. It is withheld when DQ is missing, when the product is L3, or when the background sample is too small. A packet with little evidence is not styled as a clean bill of health.

The tool never emits `CONFIRMED_REAL`, `CONFIRMED_ARTIFACT`, or an artefact probability.

## Flags are conditions, not origins

`JUMP_DET` means the ramp fit recorded a jump. Jumps are associated with cosmic rays and with other discontinuities. The evidence text says the overlap does not prove the candidate is a cosmic ray.

`SATURATED` means the saturation step flagged the pixel. Shape and brightness can be distorted. The source is not labelled saturated-star or artefact.

`DO_NOT_USE` is the handbook's recommended exclusion, including when it is OR-ed with other bits. Exclusion from a statistic is not a verdict.

A single-pixel excess can raise `RAL-MORPH-010`. That item is a `HEURISTIC_WARNING`. If `JUMP_DET` is absent, the text says so. The synthetic spike fixture is a quiet local background plus one bright pixel. It is not a measured Roman cosmic-ray profile.

## Significance

`RAL-PIX-012` is the central excess divided by the supplied error at the central pixel. It is quoted only when the central error is finite and positive, the background was measured, and the error is not wildly smaller than the data or inconsistent with a complete variance budget (`var_poisson + var_rnoise + var_flat` all present and disagreeing by more than 25% in the median).

If `var_flat` is absent, `err^2` is **not** required to equal `var_poisson + var_rnoise`. The L2 handbook says the error array includes a flat-field term that may not be stored as its own plane. roman_datamodels 1.2.0 ImageModel has `var_poisson` and not `var_rnoise`.

A missing, zero, negative, or non-finite error produces no ratio. That gap is not reported as a non-detection.

On a synthetic file the ratio's assumption string names the fixture's `uncertainty_model`. It is not a Roman calibrated variance.

## PSF

The default adapter is `none`. The evidence item is `RAL-PSF-020` / `NOT_EVALUATED` / `MISSING_REFERENCE_PSF`.

`--psf synthetic-gaussian` fits a circular Gaussian on `SYNTHETIC_TEST` data only. The kind is `SIMULATED_EXPECTATION`, `roman_calibrated` is false, and the text says it is not an STPSF or CRDS PSF. It is refused on Roman data.

`--psf stpsf` runs only when `stpsf` is installed and the file has a filter and a detector. A missing filter returns `NOT_EVALUATED` without importing a substitute model. A STPSF exception is `NOT_EVALUATED` with the error text. No Gaussian is swapped in.

An observed residual, even from a real STPSF call, does not establish an instrumental origin or an astrophysical novelty. v0.1 has not executed a successful STPSF fit in this environment: `stpsf` is not installed, and the reference data files were not downloaded.

## Multi-exposure and L3 context

Not implemented. The packet says both are `NOT_EVALUATED`. Two exposures are not compared by array index.

## Synthetic demo

Seed `20261016`, 128×128, background 10 `synthetic_counts`, noise σ = 0.8, unit string `synthetic_counts`. The error array is that constant σ (`uncertainty_model = synthetic_gaussian_sigma`). The WCS is a TAN header with 0.11 arcsec pixels, not a Roman distortion model. The spike's neighbourhood is set exactly to the background so the morphology check is deterministic.

These choices are fixtures. They are not detector measurements.

## Next work, in scientific order

1. Repeat the L2 path on an on-orbit exposure once one is public, and record the unit that is actually attached.
2. Run STPSF at the file's filter and detector position, with the reference files present, and keep the fail-closed behaviour when they are not.
3. Compare only exposures that share a checked WCS association, time, and filter. Do not add a transient label from array indices.
4. Walk an L3 `context` map back to the contributing L2 DQ arrays.
5. Read a catalogue actually written by NGRST-Discovery-Toolkit and lock the alias list to that writer. Until then the adapter stays unverified.
