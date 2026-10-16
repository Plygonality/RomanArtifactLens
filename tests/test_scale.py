"""Cropped-array scale check. This is not a claim about lazy full-detector I/O."""

from __future__ import annotations

import time
import tracemalloc
from pathlib import Path

import numpy as np

from romanartifactlens.catalogs.ingest import Candidate
from romanartifactlens.dq.definitions import load_flag_dictionary
from romanartifactlens.evidence.evaluate import evaluate_candidate
from romanartifactlens.fixtures.synthetic import save_synthetic_npz
from romanartifactlens.io.open import open_dataset
from romanartifactlens.settings import AnalysisSettings


def test_cropped_detector_scale(tmp_path: Path) -> None:
    shape = (2048, 2048)
    rng = np.random.default_rng(7)
    science = rng.normal(0.0, 1.0, size=shape).astype(np.float32)
    err = np.ones(shape, dtype=np.float32)
    dq = np.zeros(shape, dtype=np.uint32)
    dq[100, 100] = np.uint32(1)
    path = tmp_path / "crop.npz"
    save_synthetic_npz(
        path,
        {
            "science": science,
            "err": err,
            "dq": dq,
            "units": "synthetic_counts",
            "uncertainty_model": "synthetic_gaussian_sigma",
            "data_level": "SYNTHETIC",
            "seed": 7,
            "notes": "Cropped-array scale fixture, not a Roman detector readout.",
        },
    )
    del science, err, dq
    settings = AnalysisSettings(aperture_radius_px=8, min_background_pixels=20)
    dictionary = load_flag_dictionary()
    positions = [(200.0, 200.0), (400.0, 800.0), (1000.0, 1500.0), (1800.0, 300.0)]
    tracemalloc.start()
    started = time.perf_counter()
    with open_dataset(path) as dataset:
        for index, (x_value, y_value) in enumerate(positions):
            evaluate_candidate(
                dataset,
                Candidate(f"s{index}", x_value, y_value, None, None, {}),
                settings,
                dictionary,
            )
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Four full-frame copies would be about 4 * 2048^2 * 4 bytes ~ 64 MB extra on top of the
    # file load. The bound is intentionally loose and is a regression guard, not a latency budget.
    assert peak < 400_000_000
    assert elapsed < 30.0
    record = tmp_path / "scale.txt"
    record.write_text(f"peak_bytes={peak}\nelapsed_s={elapsed:.3f}\nshape={shape}\n", encoding="utf-8")
