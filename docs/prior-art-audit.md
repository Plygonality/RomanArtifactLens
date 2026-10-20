# Prior-art and dependency audit

Written before the Roman and catalogue adapters were frozen. Sibling repositories were not modified.

## Repositories

| Repository | What was visible | Boundary for RomanArtifactLens |
| --- | --- | --- |
| `Plygonality/NGRST-Discovery-Toolkit` | HTTP 404 for the credential used here. The repository is private or absent from this account. | Do not vendor it. Do not reimplement its anomaly model. Accept a user CSV. Aliases follow the column list in the project brief (`label`, `x_centroid`, `y_centroid`, `area`, `snr`, `anomaly_score`, `anomaly_percentile`, `ra`, `dec`, `known`, `reference_id`) and are **unverified** against the live writer. `anomaly_score` is stored as an external within-image ranking, not a significance and not an artefact probability. |
| `Plygonality/RomanRecover` (README title RomanRecoverer; there is no `RomanRecoverer` repository) | Public. It matches injected truth to a detection catalogue and reports completeness. Its NGRST adapter also records that the private toolkit was unreadable, and it expects `x_centroid`, `y_centroid`, `snr`, `anomaly_score`. | Do not turn this package into a second recovery benchmark. Do not score completeness. |
| `Plygonality/WCSScene` | Public Blender add-on that places images in a 2.5D scene from WCS metadata. | Do not require Blender. A reviewed candidate CSV could be consumed by another tool later. v0.1 does not call it. |
| `Plygonality/RomanArtifactLens` | This repository. It previously contained only a one-line README. | Implementation lives here. |

## Official Roman sources consulted

Retrieved 2026-10-16.

* Data-quality article, Roman User Documentation, initial publication 16 Jul 2026. DQ is a bitmask. `DO_NOT_USE` (bit 0, value 1) should be excluded even when combined with other bits. L2 carries per-pixel DQ. L3 mosaics do not, unless a user re-runs the mosaic pipeline with `propagate_dq=True`. A context array names contributing L2 exposures. Pixels with non-zero DQ are not automatically unusable.
* WFI data levels article, update 16 Dec 2025. L2 science arrays are documented as 4088×4088, `data`/`err` in DN/s, `dq` uint32, `var_poisson`, `var_rnoise`. L3 is MJy/sr with `context` and `weight`, and the published L3 table has no DQ array.
* romancal reference-file DQ table. Pixel flags from bit 0 through bit 31, with bit 14 unnamed. Group DQ uses bit 7 for `WFI18_TRANSIENT`; pixel DQ uses bit 7 for `OUTLIER`.
* `roman_datamodels` 1.2.0 `dqflags.pixel`, imported in this environment. It matches the documented snapshot flag-for-flag, including the gap at bit 14. The handbook's RC, inverse-RC, and open-pixel families are **not** separate names in this enum.
* romanisim overview. The simulator can write L1, L2, and approximate L3 ASDF, including saturation and ramp fitting. It is not a dependency of the synthetic demo. The demo NPZ files are not romanisim products.
* STPSF is the supported PSF model. It is optional. A Gaussian is not a substitute label for it.
* MAST / Roman archive docs. No observation was invented. The only Roman-format file opened for validation is the public STScI SOC **simulation** tutorial named in `roman-integration.md`.

## Installed stack actually imported

| Package | Version run here | Role |
| --- | --- | --- |
| Python | 3.12.3 | runtime |
| numpy | 2.5.4 | arrays |
| scipy | 1.18.1 | available; morphology uses photutils |
| astropy | 8.0.2 | tables, WCS, sky separation |
| matplotlib | 3.11.2 | PNG cutouts |
| photutils | 3.1.0 | `detect_sources(..., n_pixels=1)` and `SourceCatalog` |
| roman_datamodels | 1.2.0 | optional L2/L3 reader and the live DQ enum |
| asdf | 5.4.0 | pulled in by roman_datamodels |
| gwcs | 1.0.3 | WCS inside ImageModel |
| rad | 1.2.1 | pulled in by roman_datamodels 1.2.0 |
| stpsf | not installed | fail closed |
| romancal | not installed | not required; the pipeline is not reimplemented |
| romanisim | not installed | not required |

Basic CI installs `.[dev]` only. Roman and STPSF extras are opt-in.

## Schema decisions frozen from this audit

1. Synthetic files must declare `SYNTHETIC_TEST` and must not use `DN/s` or `MJy/sr` as their unit string.
2. L2 means `ImageModel`. L3 means `MosaicModel`. Absence of L3 DQ is `NOT_EVALUATED`, not "all pixels good".
3. Image DQ is decoded with the **pixel** enum only.
4. `DO_NOT_USE` is an exclusion policy for statistics. Other named bits are observed evidence and trigger `REVIEW_RECOMMENDED` when they intersect the aperture. They do not classify the candidate.
5. Unknown bits are reported. They are not mapped onto RC or open pixels.
6. `var_rnoise` is read when the opened datamodel has it. roman_datamodels 1.2.0 `ImageModel` does not define that attribute; `MosaicModel` does. The handbook L2 table lists it. The reader does not invent the missing array.
7. Science units are taken from an attached array unit. The ImageModel schema allows both `DN / s` and `MJy / sr`. If neither is attached, the packet says so.
8. NGRST anomaly columns never set the review status.
