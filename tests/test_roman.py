"""Roman datamodel checks.

``create_fake_data`` is a library fixture. It does not validate flight support.
The tutorial L2 file, when present, is an STScI SOC simulation, not an
observatory exposure. Basic CI does not download it.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from romanartifactlens.dq.decode import decompose
from romanartifactlens.dq.definitions import load_flag_dictionary
from romanartifactlens.errors import UnsupportedDatamodelError
from romanartifactlens.io.open import open_dataset

pytest.importorskip("roman_datamodels")


def test_image_model_roundtrip_is_not_flight_validation(tmp_path: Path) -> None:
    from roman_datamodels.datamodels import ImageModel

    model = ImageModel.create_fake_data(shape=(24, 20))
    model.data[...] = 1.5
    model.dq[4, 6] = np.uint32(1031)
    model.err[...] = np.float32(0.25)
    path = tmp_path / "library_image.asdf"
    model.save(path)
    model.close()
    before = path.read_bytes()
    dataset = open_dataset(path, asserted_level="L2")
    try:
        assert dataset.dataset_kind == "ROMAN_L2"
        assert dataset.data_level == "L2"
        assert dataset.units is None
        assert "DN / s" in dataset.units_note
        assert dataset.dq is not None
        decoded = decompose(int(dataset.dq[4, 6]), load_flag_dictionary())
        assert decoded.flags == ("DO_NOT_USE", "SATURATED", "JUMP_DET", "DEAD")
        assert dataset.meta["roman_validation"] == "opened_with_roman_datamodels"
        assert dataset.meta.get("observatory_product") is False
        assert dataset.var_rnoise is None
    finally:
        dataset.close()
    assert path.read_bytes() == before


def test_mosaic_model_is_not_relabelled_as_l2(tmp_path: Path) -> None:
    from roman_datamodels.datamodels import MosaicModel

    model = MosaicModel.create_fake_data(shape=(16, 16))
    path = tmp_path / "library_mosaic.asdf"
    model.save(path)
    model.close()
    dataset = open_dataset(path)
    try:
        assert dataset.dataset_kind == "ROMAN_L3"
        assert dataset.data_level == "L3"
        assert dataset.dq is None
    finally:
        dataset.close()
    with pytest.raises(UnsupportedDatamodelError):
        open_dataset(path, asserted_level="L2")


def test_generic_asdf_is_rejected(tmp_path: Path) -> None:
    asdf = pytest.importorskip("asdf")
    path = tmp_path / "generic.asdf"
    with asdf.AsdfFile({"not_roman": np.arange(4)}) as handle:
        handle.write_to(path)
    with pytest.raises(UnsupportedDatamodelError):
        open_dataset(path)


def test_ramp_model_is_unsupported(tmp_path: Path) -> None:
    from roman_datamodels.datamodels import RampModel

    try:
        model = RampModel.create_fake_data(shape=(2, 8, 8))
    except Exception as exc:  # pragma: no cover - schema may reject the shape
        pytest.skip(f"RampModel.create_fake_data is unavailable: {exc}")
    path = tmp_path / "ramp.asdf"
    model.save(path)
    model.close()
    with pytest.raises(UnsupportedDatamodelError):
        open_dataset(path)


@pytest.mark.roman_sample
def test_official_tutorial_l2_when_present() -> None:
    sample = Path(os.environ.get("ROMANARTIFACTLENS_L2_SAMPLE", "/tmp/roman_l2_sample.asdf"))
    if not sample.is_file():
        pytest.skip("STScI tutorial L2 file is not on disk; basic CI does not download it")
    from romanartifactlens.jsonutil import sha256_file

    before = sha256_file(sample)
    dataset = open_dataset(sample, asserted_level="L2")
    try:
        assert dataset.dataset_kind == "ROMAN_L2"
        assert dataset.shape == (4088, 4088)
        assert dataset.dq is not None
        assert dataset.units is None
        assert int(np.count_nonzero(dataset.dq)) > 0
        # A known multi-flag pixel from the tutorial file inspected on 2026-10-16.
        decoded = decompose(int(dataset.dq[3511, 4085]), load_flag_dictionary())
        assert "DO_NOT_USE" in decoded.flags
        assert "JUMP_DET" in decoded.flags
        assert decoded.unknown_bits == ()
    finally:
        dataset.close()
    assert sha256_file(sample) == before
