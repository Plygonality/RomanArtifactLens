# How DQ bits are read

Roman pixel DQ is a bitmask. A value of 1031 is `1 + 2 + 4 + 1024`, i.e. `DO_NOT_USE`, `SATURATED`, `JUMP_DET`, and `DEAD` together. The decoder tests `(value & bit) != 0`. It never asks whether the pixel equals one flag.

Names come from `roman_datamodels.dqflags.pixel` when that package imports. Otherwise they come from the snapshot in `dq/definitions.py`, copied from roman_datamodels 1.2.0 and checked against the romancal reference-file table on 2026-10-16. The manifest records which source was used and whether it matched the snapshot.

Bit 14 is unnamed in both sources. A set bit 14 is `UNKNOWN_DQ_BIT_14`. It is not called an RC pixel or an open pixel. The Roman DQ handbook describes those families, and says some of them also set `DO_NOT_USE`, but this enum does not give them their own names. This tool will not invent the assignment.

Pixel bit 7 is `OUTLIER`. Group DQ uses bit 7 for `WFI18_TRANSIENT`. L2 image DQ is decoded with the pixel names only. A `uint8` mask gets an explicit limitation if one is ever supplied; the synthetic fixtures and L2 `dq` arrays used here are `uint32`.

## Policies

| Policy | Flags | Effect on the packet |
| --- | --- | --- |
| `EXCLUSION` | `DO_NOT_USE` | Default statistics omit these pixels, even if other bits are set. Aperture fraction is `RAL-DQ-020`. |
| `EXPOSURE_CONDITION` | `SATURATED`, `JUMP_DET`, `DROPOUT`, `GW_AFFECTED_DATA`, `PERSISTENCE`, `AD_FLOOR`, `OUTLIER` | Reported as observed flags. `JUMP_DET` does not prove a cosmic ray. `SATURATED` does not classify the source. |
| `DETECTOR_REFERENCE` | `DEAD`, `HOT`, `WARM`, `LOW_QE`, `TELEGRAPH`, `NONLINEAR`, flat/gain/linearity gaps, `OTHER_BAD_PIXEL`, … | Observed. They can imitate or perturb a compact source. They are not an origin story. |
| `RELIABILITY` | `UNRELIABLE_*` | Observed. A significance ratio is not quoted from an error the file itself marks unreliable when that bit is the uncertainty failure mode; the bit is still listed. |
| `GEOMETRIC` | `NON_SCIENCE`, `REFERENCE_PIXEL` | Observed. |
| `RESERVED` | `RESERVED_5`, `RESERVED_6`, `RESERVED_7` | Listed by those names. No physical meaning is added. |
| `UNKNOWN` | any other bit | `UNKNOWN_DQ_BIT_<n>`. Never dropped. |

`--dq-policy` chooses the statistics mask:

* `exclude_do_not_use` (default) — the handbook recommendation
* `exclude_nonzero` — drop every non-zero DQ pixel from the sky and the segmentation
* `include_all` — DQ does not mask statistics; non-finite values still do

Any named or unknown bit inside the aperture sets the candidate to `REVIEW_RECOMMENDED`. Annulus-only flags are reported (`RAL-DQ-012`) and, under the default policy, `DO_NOT_USE` pixels are left out of the sky. They do not by themselves mark the candidate.

## L3

The handbook says archived L3 mosaics do not contain a DQ array by default. Flagged L2 pixels affect weighting, and `DO_NOT_USE` pixels are not coadded. A `context` map points at the contributing exposures. `propagate_dq=True` is a manual mosaic option, not the archive default.

v0.1 does not join context maps to L2 files. If a file is L3, the packet says the L2 meanings were not assumed. If it also has no DQ array, the status is `INSUFFICIENT_EVIDENCE`, not the reassuring status. If a bitmask is present, the bits are listed and the L3 limitation stays in the packet.

## `dq2`

Some science files carry `dq2`. The pipeline propagates those bits and does not give them the pixel-flag names. When `dq2` exists, `RAL-DQ-070` counts non-zero aperture pixels and does not decode them.
