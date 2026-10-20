"""Offline acceptance checks that do not need a Roman exposure."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from romanartifactlens.catalogs.ingest import Candidate, load_catalog
from romanartifactlens.dq.decode import decompose
from romanartifactlens.dq.definitions import DOCUMENTED_PIXEL_FLAGS, load_flag_dictionary
from romanartifactlens.dq.regions import circular_region
from romanartifactlens.evidence.evaluate import evaluate_candidate
from romanartifactlens.fixtures.synthetic import (
    build_controlled_case,
    build_demo_arrays,
    noiseless_gaussian,
    ra_wrap_scene,
    save_synthetic_npz,
)
from romanartifactlens.io.dataset import ImageDataset
from romanartifactlens.io.open import open_dataset
from romanartifactlens.io.wcsutil import SkyConverter
from romanartifactlens.jsonutil import json_safe, sha256_file
from romanartifactlens.settings import AnalysisSettings
from romanartifactlens.workflow import analyze_files

FORBIDDEN = ("CONFIRMED_REAL", "CONFIRMED_ARTIFACT", "artifact_probability")


def _dataset(scene: dict, path: Path = Path("memory.npz")) -> ImageDataset:
    return ImageDataset(
        path=path,
        dataset_kind="SYNTHETIC_TEST",
        data_level=str(scene.get("data_level", "SYNTHETIC")),
        science=np.asarray(scene["science"], dtype=np.float64),
        err=None if scene.get("err") is None else np.asarray(scene["err"], dtype=np.float64),
        dq=None if scene.get("dq") is None else np.asarray(scene["dq"], dtype=np.uint32),
        var_poisson=scene.get("var_poisson"),
        var_rnoise=scene.get("var_rnoise"),
        var_flat=scene.get("var_flat"),
        units=str(scene.get("units", "synthetic_counts")),
        units_note="synthetic",
        wcs=scene.get("wcs"),
        meta={"seed": scene.get("seed"), "roman_validation": "not_applicable_synthetic_test"},
        declaration="SYNTHETIC_TEST",
        uncertainty_model=scene.get("uncertainty_model"),
    )


def _candidate(x: float, y: float, candidate_id: str = "c") -> Candidate:
    return Candidate(candidate_id, x, y, None, None, {})


def _settings(**kwargs: object) -> AnalysisSettings:
    return AnalysisSettings(**kwargs)  # type: ignore[arg-type]


def _codes(report: dict) -> dict[str, dict]:
    return {item["code"]: item for item in report["evidence"]}


def test_combined_bits_keep_every_flag() -> None:
    dictionary = load_flag_dictionary()
    raw = DOCUMENTED_PIXEL_FLAGS["DO_NOT_USE"] | DOCUMENTED_PIXEL_FLAGS["SATURATED"]
    raw |= DOCUMENTED_PIXEL_FLAGS["JUMP_DET"] | DOCUMENTED_PIXEL_FLAGS["DEAD"]
    assert raw == 1031
    decoded = decompose(raw, dictionary)
    assert decoded.flags == ("DO_NOT_USE", "SATURATED", "JUMP_DET", "DEAD")
    assert decoded.unknown_bits == ()
    # Equality with the sum would hide the mixture. The decoder must not do that.
    assert decoded.raw != DOCUMENTED_PIXEL_FLAGS["DEAD"]


def test_unknown_bit_is_not_named() -> None:
    dictionary = load_flag_dictionary()
    decoded = decompose(DOCUMENTED_PIXEL_FLAGS["DO_NOT_USE"] | (1 << 14), dictionary)
    assert "DO_NOT_USE" in decoded.flags
    assert 14 in decoded.unknown_bits
    assert all("RC" not in name and "OPEN" not in name for name in decoded.flags)
    blob = json.dumps(decoded.to_dict())
    assert "UNKNOWN_DQ_BIT_14" in blob
    assert "fabricat" not in blob.lower()


def test_aperture_and_annulus_fractions_match_hand_count() -> None:
    shape = (12, 12)
    dq = np.zeros(shape, dtype=np.uint32)
    # Candidate at the left edge. Radius 2.5 around (x=0.2, y=5).
    x, y, radius = 0.2, 5.0, 2.5
    hand_on = []
    hand_off = 0
    for col in range(-3, 5):
        for row in range(1, 9):
            distance = float(np.hypot(col - x, row - y))
            if distance <= radius:
                if 0 <= col < 12 and 0 <= row < 12:
                    hand_on.append((row, col))
                else:
                    hand_off += 1
    region = circular_region(shape, x, y, radius, 0.0)
    assert region.n_off_image == hand_off
    assert region.n_on_image == len(hand_on)
    for row, col in hand_on:
        assert region.mask[row, col]
    assert int(region.mask.sum()) == len(hand_on)
    for row, col in hand_on:
        if col <= 1:
            dq[row, col] = np.uint32(1 | 4)
    dictionary = load_flag_dictionary()
    from romanartifactlens.dq.decode import summarize_region

    summary = summarize_region(dq, region.mask, dictionary)
    expected = sum(1 for row, col in hand_on if col <= 1)
    assert summary["flag_counts"]["DO_NOT_USE"] == expected
    assert summary["flag_counts"]["JUMP_DET"] == expected
    assert summary["flag_fractions"]["DO_NOT_USE"] == pytest.approx(expected / len(hand_on))
    annulus = circular_region(shape, x, y, radius * 2, radius)
    # The boundary pixel of the aperture is not also in the annulus.
    assert not np.any(region.mask & annulus.mask)


def test_missing_dq_is_not_a_clean_result(tmp_path: Path) -> None:
    scene = build_controlled_case(dq_value=None)
    path = tmp_path / "nodq.npz"
    save_synthetic_npz(path, scene)
    dataset = open_dataset(path)
    report = evaluate_candidate(
        dataset, _candidate(24, 24, "nodq"), _settings(aperture_radius_px=4), load_flag_dictionary()
    ).report
    assert report["overall_review_status"] == "INSUFFICIENT_EVIDENCE"
    assert _codes(report)["RAL-DQ-001"]["status"] == "MISSING_DQ"
    assert "NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS" != report["overall_review_status"]


def test_l3_without_dq_is_not_treated_as_l2(tmp_path: Path) -> None:
    scene = build_controlled_case(dq_value=None, data_level="L3")
    path = tmp_path / "l3.npz"
    save_synthetic_npz(path, scene)
    dataset = open_dataset(path)
    assert dataset.data_level == "L3"
    assert dataset.dataset_kind == "SYNTHETIC_TEST"
    report = evaluate_candidate(
        dataset, _candidate(24, 24, "l3"), _settings(aperture_radius_px=4), load_flag_dictionary()
    ).report
    assert report["overall_review_status"] == "INSUFFICIENT_EVIDENCE"
    assert _codes(report)["RAL-DQ-060"]["status"] == "L3_DQ_SEMANTICS"
    with pytest.raises(Exception) as exc:
        open_dataset(path, asserted_level="L2")
    assert getattr(exc.value, "exit_code", None) == 3


def test_coordinate_roundtrip_and_ra_wrap(tmp_path: Path) -> None:
    scene = ra_wrap_scene()
    path = tmp_path / "wrap.npz"
    save_synthetic_npz(path, scene)
    dataset = open_dataset(path)
    assert dataset.wcs is not None
    converter = SkyConverter(dataset.wcs)
    x, y = 40.0, 16.0
    ra, dec = converter.pixel_to_sky(x, y)
    back_x, back_y = converter.sky_to_pixel(ra, dec)
    assert back_x == pytest.approx(x, abs=1e-6)
    assert back_y == pytest.approx(y, abs=1e-6)
    assert ra > 350.0 or ra < 1.0
    # A catalogue RA on the other side of the branch must not jump by a full turn in pixels.
    wrapped = converter.sky_to_pixel(ra + 360.0, dec)
    assert wrapped[0] == pytest.approx(x, abs=1e-4)
    catalog = tmp_path / "wrap.csv"
    catalog.write_text("candidate_id,ra,dec\nwrap-01,{:.8f},{:.8f}\n".format(ra, dec), encoding="utf-8")
    loaded = load_catalog(catalog, dataset)
    assert loaded[0].x == pytest.approx(x, abs=1e-4)
    assert loaded[0].y == pytest.approx(y, abs=1e-4)


def test_invalid_uncertainties_do_not_invent_sigma() -> None:
    dictionary = load_flag_dictionary()
    settings = _settings(aperture_radius_px=4, min_background_pixels=10)
    cases = {
        "missing": build_controlled_case(include_err=False, spike=25),
        "zero": build_controlled_case(err_value=0.0, spike=25),
        "negative": build_controlled_case(err_value=-1.0, spike=25),
        "nonfinite": build_controlled_case(err_value=np.inf, spike=25),
        "tiny": build_controlled_case(err_value=1e-12, spike=25),
    }
    inconsistent = build_controlled_case(
        err_value=1.0,
        spike=25,
        var_poisson=100.0,
        var_rnoise=100.0,
        var_flat=100.0,
    )
    cases["inconsistent"] = inconsistent
    for name, scene in cases.items():
        report = evaluate_candidate(dataset_of(scene), _candidate(24, 24, name), settings, dictionary).report
        significance = _codes(report)["RAL-PIX-012"]
        assert significance["value"] is None, name
        assert significance["status"] != "MEASURED", name
        blob = json.dumps(json_safe(report))
        assert "5 sigma" not in blob.lower()
        assert "5σ" not in blob


def dataset_of(scene: dict) -> ImageDataset:
    wcs = None
    if "wcs_crpix" in scene:
        from romanartifactlens.io.wcsutil import tan_wcs_from_arrays

        wcs = tan_wcs_from_arrays(scene["wcs_crpix"], scene["wcs_crval"], scene["wcs_cd"])
    scene = dict(scene)
    scene["wcs"] = wcs
    return _dataset(scene)


def test_demo_candidates_have_the_expected_evidence_classes() -> None:
    scene = build_demo_arrays()
    dataset = dataset_of(scene)
    dictionary = load_flag_dictionary()
    settings = _settings(aperture_radius_px=12, min_background_pixels=30)
    reports = {}
    for row in scene["candidates"]:
        candidate = Candidate(
            str(row["candidate_id"]),
            float(row["x"]),
            float(row["y"]),
            float(row["ra"]),
            float(row["dec"]),
            {"fixture_label": row["fixture_label"], "anomaly_score": row["anomaly_score"]},
        )
        report = evaluate_candidate(dataset, candidate, settings, dictionary).report
        reports[candidate.candidate_id] = report
        blob = json.dumps(json_safe(report))
        for forbidden in FORBIDDEN:
            assert forbidden not in blob
        assert report["not_concluded"]
    clean = reports["clean-01"]
    assert clean["overall_review_status"] == "NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS"
    assert _codes(clean)["RAL-MORPH-010"]["status"] == "ABSENT"
    assert _codes(clean)["RAL-PSF-020"]["status"] == "MISSING_REFERENCE_PSF"
    assert "astrophysically real" in " ".join(clean["not_concluded"])
    jump = reports["jump-01"]
    assert jump["overall_review_status"] == "REVIEW_RECOMMENDED"
    jump_item = _codes(jump)["RAL-DQ-031"]
    assert jump_item["status"] == "PRESENT"
    assert jump_item["kind"] == "OBSERVED_FLAG"
    assert "does not prove" in jump_item["interpretation"]
    assert "cosmic ray" in jump_item["interpretation"].lower()
    edge = reports["edge-01"]
    assert edge["overall_review_status"] == "REVIEW_RECOMMENDED"
    assert edge["measurements"]["n_aperture_pixels_off_image"] > 0
    assert _codes(edge)["RAL-DQ-020"]["status"] == "PRESENT"
    spike = reports["spike-01"]
    assert spike["overall_review_status"] == "REVIEW_RECOMMENDED"
    heuristic = _codes(spike)["RAL-MORPH-010"]
    assert heuristic["kind"] == "HEURISTIC_WARNING"
    assert heuristic["status"] == "PRESENT"
    assert "not a cosmic-ray classification" in heuristic["interpretation"]
    assert "JUMP_DET" not in (spike["dq_summary"]["aperture"]["flag_counts"])
    # The external anomaly score must not become the review.
    assert spike["catalogue_metadata"]["anomaly_score"] == pytest.approx(0.93)
    assert _codes(spike)["RAL-CAT-010"]["status"] == "NOT_INTERPRETED"


def test_fixture_label_does_not_change_the_status() -> None:
    scene = build_demo_arrays()
    dataset = dataset_of(scene)
    dictionary = load_flag_dictionary()
    settings = _settings(aperture_radius_px=12)
    row = scene["candidates"][0]
    first = evaluate_candidate(
        dataset,
        Candidate("clean-01", row["x"], row["y"], None, None, {"fixture_label": "clean_point_source"}),
        settings,
        dictionary,
    ).report
    second = evaluate_candidate(
        dataset,
        Candidate("clean-01", row["x"], row["y"], None, None, {"fixture_label": "cosmic_ray"}),
        settings,
        dictionary,
    ).report
    assert first["overall_review_status"] == second["overall_review_status"]
    assert [item["code"] for item in first["evidence"]] == [item["code"] for item in second["evidence"]]


def test_psf_toy_recovers_a_noiseless_gaussian_and_is_not_called_roman() -> None:
    scene = noiseless_gaussian()
    dataset = dataset_of(scene)
    settings = _settings(
        aperture_radius_px=8,
        min_background_pixels=20,
        psf_adapter="synthetic-gaussian",
        psf_sigma_px=scene["sigma"],
    )
    report = evaluate_candidate(
        dataset, _candidate(scene["x"], scene["y"], "psf"), settings, load_flag_dictionary()
    ).report
    item = _codes(report)["RAL-PSF-020"]
    assert item["kind"] == "SIMULATED_EXPECTATION"
    assert item["status"] == "MEASURED"
    assert item["context"]["roman_calibrated"] is False
    assert item["context"]["model_name"] == "synthetic_gaussian_toy"
    assert item["context"]["amplitude"] == pytest.approx(scene["amplitude"], rel=0.02)
    assert abs(item["context"]["dx_px"]) <= 0.15
    assert abs(item["context"]["dy_px"]) <= 0.15
    assert "not an STPSF" in item["interpretation"] or "not a Roman PSF" in item["interpretation"]


def test_stpsf_without_filter_is_not_evaluated_and_not_a_gaussian() -> None:
    scene = build_controlled_case(spike=10)
    dataset = dataset_of(scene)
    dataset.meta["detector"] = None
    dataset.meta["optical_element"] = None
    settings = _settings(aperture_radius_px=4, min_background_pixels=10, psf_adapter="stpsf")
    report = evaluate_candidate(
        dataset, _candidate(24, 24, "psf"), settings, load_flag_dictionary()
    ).report
    item = _codes(report)["RAL-PSF-020"]
    assert item["status"] == "MISSING_REFERENCE_PSF"
    assert item["context"]["model_name"] is None
    assert "Gaussian" in item["interpretation"]


def test_repeatability_and_input_hash(tmp_path: Path) -> None:
    from romanartifactlens.fixtures.synthetic import write_demo_files

    files = write_demo_files(tmp_path / "scene")
    before = sha256_file(files["image"])
    settings = _settings(aperture_radius_px=12)
    first = analyze_files(files["image"], files["catalog"], tmp_path / "a", settings, command="one")
    second = analyze_files(files["image"], files["catalog"], tmp_path / "b", settings, command="two")
    assert sha256_file(files["image"]) == before
    ids_a = [packet.report["candidate_id"] for packet in first["packets"]]
    ids_b = [packet.report["candidate_id"] for packet in second["packets"]]
    assert ids_a == ids_b == ["clean-01", "jump-01", "edge-01", "spike-01"]
    for left, right in zip(first["packets"], second["packets"], strict=True):
        assert json_safe(left.report) == json_safe(right.report)
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"][0]["sha256"] == before
    assert manifest["flag_definitions"]["source"]
    assert manifest["reference_model"]["roman_calibrated_psf"] is False


def test_schema_errors(tmp_path: Path) -> None:
    from romanartifactlens.errors import InvalidDataError

    bad = tmp_path / "bad.npz"
    np.savez(bad, declaration=np.array("SYNTHETIC_TEST"), science=np.zeros(5))
    with pytest.raises(InvalidDataError):
        open_dataset(bad)
    scene = build_controlled_case()
    scene["dq"] = np.zeros((4, 4), dtype=np.uint32)
    image = tmp_path / "shape.npz"
    with pytest.raises(InvalidDataError):
        save_synthetic_npz(image, scene)
        open_dataset(image)
    good = tmp_path / "good.npz"
    save_synthetic_npz(good, build_controlled_case())
    catalog = tmp_path / "missing.csv"
    catalog.write_text("candidate_id,note\nonly-a-name,x\n", encoding="utf-8")
    with pytest.raises(InvalidDataError):
        analyze_files(good, catalog, tmp_path / "out", _settings(), command="test")
    calibrated = tmp_path / "units.npz"
    scene = build_controlled_case(units="DN/s")
    save_synthetic_npz(calibrated, scene)
    with pytest.raises(InvalidDataError):
        open_dataset(calibrated)


def test_ngrst_alias_fixture_is_marked_unverified(tmp_path: Path) -> None:
    from romanartifactlens.fixtures.synthetic import write_demo_files

    files = write_demo_files(tmp_path)
    dataset = open_dataset(files["image"])
    loaded = load_catalog(files["ngrst_catalog"], dataset)
    assert [item.candidate_id for item in loaded] == ["clean-01", "jump-01", "edge-01", "spike-01"]
    assert loaded[0].x == pytest.approx(40.0)
    assert "unverified" in str(loaded[0].catalogue_metadata["metadata_note"]).lower()
    assert loaded[-1].catalogue_metadata["anomaly_score"] == pytest.approx(0.93)


def test_pixel_coordinate_reads_array_yx() -> None:
    scene = build_controlled_case(science_value=0.0, spike=7.0, x=3, y=5)
    dataset = dataset_of(scene)
    assert dataset.science[5, 3] == pytest.approx(7.0)
    assert dataset.science[3, 5] == pytest.approx(0.0)
