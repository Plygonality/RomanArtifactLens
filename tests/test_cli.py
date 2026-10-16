from __future__ import annotations

import json
from pathlib import Path

from romanartifactlens.cli import main
from romanartifactlens.fixtures.synthetic import write_demo_files
from romanartifactlens.jsonutil import sha256_file


def test_cli_workflows(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["demo", "--out", str(demo), "--radius-px", "12"]) == 0
    index = demo / "reports" / "index.html"
    assert index.is_file()
    assert "SYNTHETIC_TEST" in index.read_text(encoding="utf-8")
    image = demo / "synthetic_image.npz"
    before = sha256_file(image)
    inspect_code = main(["inspect", str(image)])
    assert inspect_code == 0
    flags = main(["flags", str(image), "--x", "62", "--y", "41"])
    assert flags == 0
    out = tmp_path / "reports"
    analyze = main(
        [
            "analyze",
            str(image),
            "--catalog",
            str(demo / "candidates.csv"),
            "--radius-px",
            "12",
            "--out",
            str(out),
        ]
    )
    assert analyze == 0
    assert sha256_file(image) == before
    assert main(["report", str(out), "--format", "html"]) == 0
    evidence = json.loads((out / "candidates" / "jump-01" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["overall_review_status"] == "REVIEW_RECOMMENDED"
    assert any(item["code"] == "RAL-DQ-031" for item in evidence["evidence"])
    spike = json.loads((out / "candidates" / "spike-01" / "evidence.json").read_text(encoding="utf-8"))
    text = json.dumps(spike)
    assert "CONFIRMED_ARTIFACT" not in text
    assert "not a cosmic-ray classification" in text
    review = (out / "candidates" / "clean-01" / "review.html").read_text(encoding="utf-8")
    assert "cutout_science.png" not in review or "data:image/png;base64" in review
    assert main(["doctor"]) == 0
    assert main(["explain-diagnostic", "RAL-DQ-031"]) == 0
    assert main(["explain-diagnostic", "RAL-NO-SUCH"]) == 2
    assert main(["flags", str(image), "--x", "-50", "--y", "1"]) == 2


def test_flags_pixel_matches_documented_sum(tmp_path: Path, capsys) -> None:
    files = write_demo_files(tmp_path)
    assert main(["flags", str(files["image"]), "--x", "62", "--y", "41"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["raw_dq"] == 1031
    assert payload["flags"] == ["DO_NOT_USE", "SATURATED", "JUMP_DET", "DEAD"]
    assert payload["unknown_bits"] == []


def test_inspect_does_not_dump_pixels(tmp_path: Path, capsys) -> None:
    files = write_demo_files(tmp_path)
    assert main(["inspect", str(files["image"])]) == 0
    text = capsys.readouterr().out
    assert "SYNTHETIC_TEST" in text
    assert "does not print the science array" in text
    assert len(text) < 20000
