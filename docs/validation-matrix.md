# Validation matrix

Local run on 2026-10-16, Python 3.12.3, `pytest` from a virtualenv with `.[roman]` installed so the Roman tests could execute. Result: **24 passed, 0 failed, 0 skipped**.

Basic CI (`.github/workflows/tests.yml`) installs `.[dev]` only, on Python 3.11 and 3.12, and runs `ruff check` and `pytest`. In that environment `tests/test_roman.py` skips because `roman_datamodels` is absent, and the tutorial-file test skips unless the ASDF is already on disk. CI does not download it.

| # | Check | Result |
| --- | --- | --- |
| 1 | DQ combination. Value 1031 reports `DO_NOT_USE`, `SATURATED`, `JUMP_DET`, and `DEAD`. | Passed. `flags` on `examples/synthetic_image.npz` at `(62, 41)` returns those four names. |
| 2 | Unknown bits. Bit 14 OR `DO_NOT_USE` keeps both, and does not invent an RC/open name. Dictionary provenance is in the manifest. Installed 1.2.0 matches the snapshot (`snapshot_matches_installed: true`). | Passed. |
| 3 | Aperture and annulus fractions, including a partially off-image aperture, match an independent pixel-center count. The shared boundary stays in the aperture. | Passed. |
| 4 | Missing DQ is `MISSING_DQ` and `INSUFFICIENT_EVIDENCE`. An NPZ tagged `data_level=L3` is not accepted as L2 (`--data-level L2` exits 3). A `MosaicModel` opens as L3 with no DQ. | Passed. |
| 5 | 0-based `(x, y)` maps to `science[y, x]`. TAN WCS round-trips, including a pixel whose RA falls near 359.9° and a +360° catalogue RA. | Passed. |
| 6 | Missing, zero, negative, non-finite, tiny, and variance-inconsistent errors do not produce `RAL-PIX-012` value. | Passed. |
| 7 | `clean-01` is `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS`. PSF is `NOT_EVALUATED`. The packet still says it does not establish astrophysical reality. Changing the fixture label does not change the status. | Passed. |
| 8 | `jump-01` emits `RAL-DQ-031` (`OBSERVED_FLAG`, fraction ≈ 0.0295) and does not set `DO_NOT_USE`. `edge-01` reports off-image pixels and a `DO_NOT_USE` fraction ≈ 0.152. | Passed. |
| 9 | `spike-01` raises `RAL-MORPH-010` and has no `JUMP_DET` in the aperture. The text says it is not a cosmic-ray classification. | Passed. |
| 10 | Noiseless synthetic Gaussian, `--psf synthetic-gaussian` with the injected σ: amplitude within 2%, offset within 0.15 px, model name `synthetic_gaussian_toy`, `roman_calibrated` false. STPSF with no filter returns `MISSING_REFERENCE_PSF` and does not attach a Gaussian. A successful STPSF fit was **not** run. | Passed for the toy and the fail-closed path. STPSF success is not claimed. |
| 11 | Two analyses of the same NPZ produce equal evidence JSON, the same candidate ids, and a manifest whose image SHA-256 matches the file. | Passed. |
| 12 | SHA-256 of the NPZ and of the tutorial ASDF are unchanged after inspect/analyze/open. | Passed. |
| 13 | 1-D science, DQ shape mismatch, missing catalogue coordinates, and synthetic units `DN/s` raise `InvalidDataError` (exit 2). | Passed. |
| 14 | `examples/ngrst_candidates.csv` is read through `label`, `x_centroid`, `y_centroid`. The metadata note says the live toolkit was not verified. `anomaly_score` 0.93 on the spike does not set the status. | Passed. Live repository was HTTP 404. |
| 15 | Real supported product. The SOC tutorial L2 file above was opened with `roman_datamodels` 1.2.0, has a genuine DQ array, and decodes `DO_NOT_USE`+`JUMP_DET` at `(4085, 3511)`. `create_fake_data` is a separate interface test and is not counted as flight validation. No on-orbit exposure was available. | Passed for the tutorial simulation. Flight data: not tested. |
| 16 | 2048×2048 synthetic crop, 4 candidates: tracemalloc peak ≈ 121 MB, ≈ 2.3 s. Tutorial 4088×4088 open + one candidate: tracemalloc peak ≈ 360 MB, RSS ≈ 468 MB. Full-frame lazy processing is not claimed. | Passed as a measurement, with that limit. |

## Demo packet

`examples/review/` was produced by:

```bash
romanartifactlens analyze examples/synthetic_image.npz \
  --catalog examples/candidates.csv --radius-px 12 \
  --out examples/review
```

Image SHA-256 `f3a218cd94dc2039fd5c62f7dedc5681425301d0ca1e8166cbba41c06465869c`.

Seed `20261016`. Flag source `roman_datamodels.dqflags.pixel` 1.2.0. PSF adapter `none`.

| ID | Status |
| --- | --- |
| clean-01 | `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS` |
| jump-01 | `REVIEW_RECOMMENDED` (`JUMP_DET`) |
| edge-01 | `REVIEW_RECOMMENDED` (`DO_NOT_USE`, truncated aperture) |
| spike-01 | `REVIEW_RECOMMENDED` (isolated-pixel heuristic, significance ratio quoted only under the synthetic error model) |
