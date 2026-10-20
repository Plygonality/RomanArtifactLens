# Data contract

Schema version of the evidence packet: `1.0.0`.

## Images

### Synthetic NPZ

Required:

* `declaration`: the string `SYNTHETIC_TEST`
* `science`: 2-D numeric array

Optional:

* `err`, `dq` (integer, values in `uint32`), `dq2`, `var_poisson`, `var_rnoise`, `var_flat`
* `units`: must start with `synthetic` or be `dimensionless`
* `data_level`: free string such as `SYNTHETIC` or `L3`. It does not make the file a Roman product. `dataset_kind` remains `SYNTHETIC_TEST`.
* `uncertainty_model`: short label for the error array the fixture author actually wrote
* `seed`, `notes`
* `wcs_crpix` (0-based x, y), `wcs_crval` (degrees), `wcs_cd` (2×2 CD matrix, degrees)

A synthetic file that claims units `DN/s` or `MJy/sr` is rejected.

### Roman ASDF

Opened only with `roman_datamodels.open`. Recognised types:

| Datamodel | Level | Behaviour |
| --- | --- | --- |
| `ImageModel` | L2 | Read `data`, `err`, `dq`, `dq2` if present, and variance planes that exist. |
| `MosaicModel` | L3 | Opened so the report can say DQ was not evaluated as L2. A missing DQ array is not treated as zeros. |
| `RampModel`, `ScienceRawModel`, guide-window models | L1 | Rejected (exit 3). |
| Anything else, including a generic ASDF tree | — | Rejected (exit 3). |

`--data-level L2` must match the opened type. A mismatch is exit 3 rather than a reinterpretation.

## Coordinates

* Catalogue `x` increases with column index. `y` increases with row index.
* The array sample is `science[y, x]` when `x` and `y` are integers.
* Integer coordinates are **pixel centers**. The center of the first pixel is `(0, 0)`, matching Astropy's high-level WCS API. FITS `CRPIX` inside the synthetic builder is stored 1-based, and the converter adds 1 when it constructs that WCS.
* The central pixel of a fractional position uses NumPy round-half-to-even (`np.round`).
* A pixel center is inside an aperture when its distance to `(x, y)` is `<= radius`. The aperture boundary belongs to the aperture, not the annulus. The annulus is `inner < distance <= outer`. The default annulus is `radius` to `2 * radius`.
* Off-image pixel centers are counted and are not filled with zeros or with DQ `0`.
* `ra` is normalised to `[0, 360)` degrees. Sky and pixel coordinates, when both are present, must agree within `--coordinate` tolerance (default 0.05 arcsec) or the row is an error.
* Two files are not compared by sharing array indices. v0.1 does not do multi-exposure matching.

## Catalogue aliases

Identifier, first match only: `candidate_id`, `id`, `label`, `source_id`, `name`.

Pixel: `x`/`y`, or `x_centroid`/`y_centroid`, or `x_pix`/`y_pix`, or `xcenter`/`ycenter`. If two aliases for the same axis both exist, the file is rejected.

Sky: `ra`/`dec` or `ra_deg`/`dec_deg`.

Duplicate ids are rejected. Other columns are metadata. `anomaly_score` produces evidence code `RAL-CAT-010` with status `NOT_INTERPRETED`.

## Evidence item

```text
code, kind, status, description, interpretation,
source_field, value, threshold_or_policy, confidence_class, context
```

`kind` is one of `OBSERVED_FLAG`, `DERIVED_METRIC`, `HEURISTIC_WARNING`, `SIMULATED_EXPECTATION`, `NOT_EVALUATED`, `UNAVAILABLE`.

Overall status is one of:

* `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS` — DQ was read, the background sample was large enough, and no aperture flag, unknown bit, non-finite pixel, edge truncation, invalid error, or isolated-pixel heuristic fired. Unchecked items (PSF, multi-exposure) remain visible.
* `REVIEW_RECOMMENDED` — at least one of those checks fired. This asks a person to look. It is not a classification.
* `INSUFFICIENT_EVIDENCE` — the candidate is off the image, DQ was never read, the level is L3, or the background sample is too small, and nothing stronger already forced a review.

## Manifest

`manifest.json` records `schema_version`, UTC time, the command line, package versions, input path/size/SHA-256, flag-dictionary provenance, PSF adapter (`roman_calibrated_psf` is false unless a future version has a real calibrated fit and says so), analysis settings, and dataset-level limitations.

Repeating a run on the same bytes and settings repeats the evidence JSON. The manifest timestamp and the recorded command may differ.
