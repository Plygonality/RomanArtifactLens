# Examples

Everything in this directory is a **SYNTHETIC_TEST**. The NPZ declaration says so. There is no Roman observation identifier and the unit string is `synthetic_counts`.

`synthetic_image.npz`, `candidates.csv`, `ngrst_candidates.csv`, and `run.json` are written by `romanartifactlens.fixtures` with seed `20261016`. Regenerate them with:

```bash
romanartifactlens demo --out build/demo
```

That command also writes a fresh report under `build/demo/reports`. The packet checked into `review/` is the output of:

```bash
romanartifactlens analyze examples/synthetic_image.npz \
  --catalog examples/candidates.csv --radius-px 12 \
  --out examples/review
```

`ngrst_candidates.csv` uses the unverified NGRST-style aliases (`label`, `x_centroid`, `y_centroid`, `anomaly_score`, …). `run.json` is hashed when it sits beside the catalogue and is not interpreted.

`review/index.html` is the multi-candidate page. Each `review/candidates/<id>/review.html` embeds the cutout PNGs. The numeric cutout is `cutout_science.npy` and `cutout_science.csv`. The colour scale in the PNG is a display stretch; the files keep the original values.

Pixel `(x=62, y=41)` has DQ 1031 and is not one of the four catalogue rows. Inspect it with:

```bash
romanartifactlens flags examples/synthetic_image.npz --x 62 --y 41
```
