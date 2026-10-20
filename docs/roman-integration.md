# Roman integration

## What counts as support

v0.1 can open a file that `roman_datamodels` recognises as an `ImageModel` or a `MosaicModel`. A library fake (`create_fake_data`) checks the interface and is **not** observatory validation. A mock DQ array written by this package is not a Roman calibration product.

## What was opened

### Library round trip

`ImageModel.create_fake_data` from roman_datamodels 1.2.0 was saved, given DQ value 1031 at one pixel, and reopened. The reader reported level L2, kind `ROMAN_L2`, units `null` (the ndarray had no unit), and the four flag names. `var_rnoise` was absent. The file bytes were unchanged after the read. `MosaicModel.create_fake_data` opened as L3 with `dq is None`. A generic ASDF tree and a `RampModel` were rejected. This is an interface test.

### STScI SOC simulation tutorial

Public object, not invented:

```text
s3://stpubdata/roman/nexus/soc_simulations/tutorial_data/roman-2026.2/r0003201001001001004_0001_wfi01_f106_cal.asdf
```

HTTPS download used for the local test:

```text
https://stpubdata.s3.amazonaws.com/roman/nexus/soc_simulations/tutorial_data/roman-2026.2/r0003201001001001004_0001_wfi01_f106_cal.asdf
```

SHA-256 `c59d9c060e40dc20933b6e863e48e8b72edc88b94cc0f59e9163dd36f4fb77fa`, 204,787,760 bytes. The file is not in git.

`roman_datamodels` 1.2.0 opened it as `ImageModel`, shape `(4088, 4088)`.

| Plane | dtype | Notes |
| --- | --- | --- |
| `data` | float32 | No array unit attached. Schema allows `DN / s` or `MJy / sr`. Neither was applied. |
| `err` | float16 | Finite on most pixels; some non-finite values, including one infinity. |
| `dq` | uint32 | 685,538 non-zero pixels. No unknown bits against the 1.2.0 enum. |
| `var_poisson` | float16 | Present. |
| `var_rnoise`, `var_flat` | — | Not attributes of this ImageModel. |
| `dq2` | — | Not in this file's tree. The fake ImageModel from the same library does have `dq2`. |

Metadata read from the file: detector `WFI01`, optical element `F106`, exposure type `WFI_IMAGE`, origin `STSCI/SOC`, calibration software `RomanCAL` `1.0.1`. `photometry.conversion_megajanskys` on the library fake is a sentinel; this tutorial file was not relabelled into MJy/sr.

Named DQ bits with non-zero counts in that file: `DO_NOT_USE` (15,533), `SATURATED` (11,782), `JUMP_DET` (24,182), `DEAD` (15,366), `LOW_QE` (650,508), `NONLINEAR` (7,911), `NO_LIN_CORR` (17,062), `UNRELIABLE_FLAT` (15,847).

Pixel `(x=4085, y=3511)` carries `DO_NOT_USE` and `JUMP_DET` among its bits (raw value 34,604,037). The test checks those two names and that no unknown bit is set. A bright finite pixel at `(3391, 3606)` has central DQ 0 and still received `REVIEW_RECOMMENDED` because the aperture overlaps `LOW_QE`. That is the intended behaviour: a clear central pixel is not a clean neighbourhood.

`roman_datamodels` warns that `meta.filename` does not match the local basename and patches the name **in memory**. The on-disk SHA-256 was unchanged after `open` and after `close`. The reader does not call `save`.

## Memory

Measured while opening the tutorial file and evaluating one 8-pixel-radius candidate, Python 3.12.3, roman_datamodels 1.2.0, `memmap=True`:

* reader alone: tracemalloc peak about 222 MB, RSS about 336 MB
* reader plus one candidate: tracemalloc peak about 360 MB, RSS about 468 MB
* open about 5 s, the cutout evaluation about 0.5 s

The arrays are not processed fully out of core. `roman_datamodels` materialises `data`, `err`, `dq`, and `var_poisson` when those attributes are read. Cutouts copy only the window. Full-frame `float64` copies of the science image are not made.

A 2048×2048 synthetic crop, four candidates, radius 8 px: tracemalloc peak about 121 MB, elapsed about 2.3 s including the NPZ read. That is a cropped-array check, not a promise about every future full-detector file.

## How to run a file you have

```bash
pip install -e ".[roman]"
romanartifactlens inspect data/roman_l2.asdf
romanartifactlens analyze data/roman_l2.asdf \
  --catalog data/candidates.csv --data-level L2 --out reports/roman
```

Basic CI does not download the tutorial file. `tests/test_roman.py` skips `test_official_tutorial_l2_when_present` unless `ROMANARTIFACTLENS_L2_SAMPLE` or `/tmp/roman_l2_sample.asdf` exists. The library round-trip tests skip when `roman_datamodels` is not installed.

## Not validated

* No on-orbit Roman exposure was opened.
* STPSF was not run.
* romancal was not run. This package does not reimplement the exposure pipeline.
* L3 `context` was not joined to L2 inputs.
* The tutorial product is a SOC simulation distributed for the Roman Research Nexus notebooks.
