# Changelog

## 0.1.0

First usable evidence inspector for one candidate position.

* Synthetic NPZ reader that accepts only `SYNTHETIC_TEST` and refuses calibrated unit strings.
* Roman ASDF reader for `roman_datamodels` `ImageModel` (L2) and `MosaicModel` (L3). Generic ASDF and L1 ramps are rejected. L3 is not relabelled as L2.
* Bitwise DQ decoding from the installed `roman_datamodels.dqflags.pixel` table, with a roman_datamodels 1.2.0 snapshot when that package is absent. Unknown bits stay `UNKNOWN_DQ_BIT`.
* Cutouts, annulus background, uncertainty checks that refuse a significance when the error array is missing or invalid, and photutils segmentation.
* Optional PSF path: no model by default (`NOT_EVALUATED`); a synthetic Gaussian toy only on `SYNTHETIC_TEST`; STPSF only with filter and detector metadata, failing closed otherwise.
* JSON, CSV/ECSV, PNG, and HTML packets with input hashes and software versions.
* CLI: `demo`, `inspect`, `flags`, `analyze`, `report`, `doctor`, `explain-diagnostic`.

Not in this version: multi-exposure comparison, L3 context-to-L2 joins, and a calibrated Roman PSF in the default demo.
