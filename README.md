# RomanArtifactLens

RomanArtifactLens builds a **candidate-level evidence packet** for one position in a Roman Wide Field Instrument image. Given a calibrated L2 exposure, or a clearly marked synthetic test image, plus a catalogue of positions, it reports the data-quality bits under that position, the local background, and what cannot be concluded.

It does not decide that a source is real, instrumental, cosmic-ray, extragalactic, or new. A DQ flag records a pipeline or reference-file condition. A pixel with no flag is not automatically clean.

## Five-minute tutorial

Python 3.11 or 3.12. No account, API key, or network is required for the synthetic demo.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

romanartifactlens demo --out build/demo
romanartifactlens inspect examples/synthetic_image.npz
romanartifactlens flags examples/synthetic_image.npz --x 62 --y 41
romanartifactlens analyze examples/synthetic_image.npz \
  --catalog examples/candidates.csv --radius-px 12 --out reports/demo
romanartifactlens report reports/demo --format html
romanartifactlens doctor
```

`build/demo/reports/index.html` and `examples/review/index.html` are the same kind of packet. Both are **SYNTHETIC_TEST** scenes generated with seed `20261016`. They are not Roman observations.

Open `examples/review/index.html`. The four candidates are:

| Candidate | Fixture label | Review status | What the packet actually shows |
| --- | --- | --- | --- |
| `clean-01` | clean point source | `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS` | No DQ bits in the aperture. PSF comparison is `NOT_EVALUATED`. This is not a confirmation that the source is astrophysical. |
| `jump-01` | jump-flag overlap | `REVIEW_RECOMMENDED` | `JUMP_DET` covers about 2.9% of the aperture pixel centers. The flag does not prove a cosmic ray. `DO_NOT_USE` is absent on this source. |
| `edge-01` | edge and invalid mask | `REVIEW_RECOMMENDED` | Part of the aperture is off the image. `DO_NOT_USE` covers about 15% of the on-image aperture. |
| `spike-01` | single-pixel spike, no jump flag | `REVIEW_RECOMMENDED` | Morphology heuristic `RAL-MORPH-010`. There is no `JUMP_DET` bit. The program does not call it a cosmic ray. |

Pixel `(x=62, y=41)` is not one of those sources. Its DQ value is `1031`, which is `DO_NOT_USE | SATURATED | JUMP_DET | DEAD`.

## Install

```bash
pip install -e ".[dev]"      # synthetic NPZ, tests, ruff
pip install -e ".[roman]"    # roman_datamodels, asdf, gwcs
pip install -e ".[psf]"      # optional STPSF; not used unless --psf stpsf
```

Core libraries are NumPy, SciPy, Astropy, Matplotlib, and Photutils. The synthetic path does not import `roman_datamodels`.

## Commands and exit codes

| Code | Meaning |
| --- | --- |
| 0 | The command finished and wrote its outputs. Individual checks may still be `NOT_EVALUATED`. |
| 1 | Unexpected internal failure. |
| 2 | Invalid inputs: missing coordinates, bad shapes, synthetic units that pretend to be calibrated. |
| 3 | Unsupported datamodel or a requested data level that does not match the file. |
| 4 | A requested optional reader is not installed (`--require roman`, `--psf stpsf` with metadata present but no STPSF). |
| 5 | `--strict`, and a candidate is `INSUFFICIENT_EVIDENCE`, DQ is missing, or a requested PSF adapter did not measure a model. |

An unrequested PSF check stays `NOT_EVALUATED` and does not by itself change the exit code. `--strict` does not treat that gap as a failure.

`inspect` prints shapes, dtypes, level, units, WCS presence, and the DQ dictionary source. It does not print the science array.

## What a packet contains

For each candidate:

* science cutout in the file's numeric values (`cutout_science.npy` and `.csv`) and a separate asinh display
* DQ overlay (red `DO_NOT_USE`, orange `JUMP_DET`, gold `SATURATED`, purple any other set bit)
* uncertainty cutout when an error array exists
* an evidence list whose `kind` is one of `OBSERVED_FLAG`, `DERIVED_METRIC`, `HEURISTIC_WARNING`, `SIMULATED_EXPECTATION`, `NOT_EVALUATED`, `UNAVAILABLE`
* overall status `NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS`, `REVIEW_RECOMMENDED`, or `INSUFFICIENT_EVIDENCE`

There is no `artifact_probability`. The statuses `CONFIRMED_REAL` and `CONFIRMED_ARTIFACT` are not used.

The manifest records input SHA-256 hashes, software versions, the flag dictionary, the coordinate convention, and the analysis settings.

## Data that v0.1 will read

* A `.npz` whose `declaration` is exactly `SYNTHETIC_TEST`, with a `synthetic_*` or `dimensionless` unit string.
* A Roman ASDF file that `roman_datamodels` opens as an `ImageModel` (L2) or a `MosaicModel` (L3, DQ not treated as L2).

Generic ASDF is rejected. L1 ramps are rejected. An L3 mosaic without a DQ array is `INSUFFICIENT_EVIDENCE`, not a clean image.

Catalogue columns may be `candidate_id` / `label` / `id` and `x`,`y` or `x_centroid`,`y_centroid`, or `ra`,`dec` when a WCS exists. Pixel coordinates are **0-based pixel centers**, `x` = column, `y` = row.

NGRST-style `anomaly_score` is stored and not interpreted. The private NGRST-Discovery-Toolkit repository was not readable here, so that alias list is unverified. See [docs/prior-art-audit.md](docs/prior-art-audit.md).

## Roman L2 status

The reader was exercised on `roman_datamodels` 1.2.0 and on the STScI SOC **simulation** tutorial file `r0003201001001001004_0001_wfi01_f106_cal.asdf` (not an observatory exposure). The science array did not carry a single unit, so the tool does not label it DN/s or MJy/sr. Details and the memory measurement are in [docs/roman-integration.md](docs/roman-integration.md).

```bash
romanartifactlens analyze data/roman_l2.asdf \
  --catalog data/candidates.csv --data-level L2 --out reports/roman
```

Use that command only with a file you actually have. This repository does not ship Roman data.

## Documentation

* [docs/prior-art-audit.md](docs/prior-art-audit.md) — NGRST, RomanRecoverer, WCSScene, and official Roman docs before the adapters were frozen
* [docs/data-contract.md](docs/data-contract.md) — files, coordinates, evidence schema
* [docs/dq-interpretation.md](docs/dq-interpretation.md) — bitmask policy
* [docs/scientific-limitations.md](docs/scientific-limitations.md) — what the tool will not conclude
* [docs/roman-integration.md](docs/roman-integration.md) — what was actually opened
* [docs/validation-matrix.md](docs/validation-matrix.md) — acceptance checks and measurements

## Privacy

Core commands do not phone home, do not need a token, and do not download MAST or CRDS files. `doctor` only reports what is already installed.

## Licence

MIT. See [LICENSE](LICENSE).
