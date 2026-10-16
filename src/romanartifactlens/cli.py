"""Command line interface for romanartifactlens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from romanartifactlens import __version__
from romanartifactlens.doctor import doctor_report
from romanartifactlens.dq.decode import decompose, summarize_region
from romanartifactlens.dq.definitions import load_flag_dictionary
from romanartifactlens.dq.regions import circular_region, nearest_pixel
from romanartifactlens.errors import (
    InvalidDataError,
    OptionalDependencyError,
    RomanArtifactLensError,
)
from romanartifactlens.evidence.codes import EXPLANATIONS, explain
from romanartifactlens.fixtures.synthetic import DEMO_SEED, write_demo_files
from romanartifactlens.io.open import open_dataset
from romanartifactlens.jsonutil import json_safe
from romanartifactlens.reports.export import rebuild_html
from romanartifactlens.settings import AnalysisSettings
from romanartifactlens.workflow import analyze_files


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except RomanArtifactLensError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        print(f"internal error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="romanartifactlens",
        description=(
            "Candidate-level artefact evidence for Roman WFI images. "
            "The tool does not classify a source as real or artificial."
        ),
    )
    parser.add_argument("--version", action="version", version=f"romanartifactlens {__version__}")
    commands = parser.add_subparsers(dest="command")

    demo = commands.add_parser("demo", help="Write a synthetic scene and its evidence packet")
    demo.add_argument("--out", required=True, type=Path)
    demo.add_argument("--radius-px", type=float, default=12.0)
    demo.add_argument("--seed", type=int, default=DEMO_SEED)
    demo.set_defaults(handler=cmd_demo)

    inspect = commands.add_parser("inspect", help="Summarise arrays, level, units, WCS, and DQ")
    inspect.add_argument("image", type=Path)
    inspect.add_argument("--data-level", default=None)
    inspect.set_defaults(handler=cmd_inspect)

    flags = commands.add_parser("flags", help="Decode the DQ value at one pixel")
    flags.add_argument("image", type=Path)
    flags.add_argument("--x", required=True, type=float)
    flags.add_argument("--y", required=True, type=float)
    flags.add_argument("--radius-px", type=float, default=None)
    flags.set_defaults(handler=cmd_flags)

    analyze = commands.add_parser("analyze", help="Build an evidence packet for a catalogue")
    _add_analyze_arguments(analyze)
    analyze.set_defaults(handler=cmd_analyze)

    report = commands.add_parser("report", help="Rebuild HTML (and the table) from an analysis directory")
    report.add_argument("directory", type=Path)
    report.add_argument("--format", default="html", choices=["html"])
    report.set_defaults(handler=cmd_report)

    doctor = commands.add_parser("doctor", help="Show installed readers without downloading data")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--require", action="append", default=[], choices=["roman", "stpsf"])
    doctor.set_defaults(handler=cmd_doctor)

    explain_cmd = commands.add_parser("explain-diagnostic", help="Explain one stable diagnostic code")
    explain_cmd.add_argument("code")
    explain_cmd.set_defaults(handler=cmd_explain)
    return parser


def _add_analyze_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("image", type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--radius-px", type=float, default=8.0)
    parser.add_argument("--annulus-inner-px", type=float, default=None)
    parser.add_argument("--annulus-outer-px", type=float, default=None)
    parser.add_argument(
        "--dq-policy",
        default="exclude_do_not_use",
        choices=["exclude_do_not_use", "exclude_nonzero", "include_all"],
    )
    parser.add_argument(
        "--background",
        default="sigma_clip_median",
        choices=["sigma_clip_median", "median"],
    )
    parser.add_argument("--min-background-pixels", type=int, default=30)
    parser.add_argument("--psf", default="none", choices=["none", "synthetic-gaussian", "stpsf"])
    parser.add_argument("--psf-sigma", type=float, default=None)
    parser.add_argument("--data-level", default=None)
    parser.add_argument("--strict", action="store_true")


def cmd_demo(args: argparse.Namespace) -> int:
    files = write_demo_files(args.out, seed=args.seed)
    settings = _settings_from_args(args)
    command = " ".join(sys.argv)
    analyze_files(
        files["image"],
        files["catalog"],
        args.out / "reports",
        settings,
        command=command,
    )
    print(f"SYNTHETIC_TEST demo written to {args.out}")
    print(f"image: {files['image']}")
    print(f"catalog: {files['catalog']}")
    print(f"report: {args.out / 'reports' / 'index.html'}")
    print("This scene is not a Roman observation.")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    with open_dataset(args.image, asserted_level=args.data_level) as dataset:
        dictionary = load_flag_dictionary()
        summary = {
            "path": str(dataset.path),
            "dataset_kind": dataset.dataset_kind,
            "data_level": dataset.data_level,
            "declaration": dataset.declaration,
            "shape": list(dataset.shape),
            "units": dataset.units,
            "units_note": dataset.units_note,
            "uncertainty_model": dataset.uncertainty_model,
            "wcs": dataset.wcs is not None,
            "dq_present": dataset.dq is not None,
            "err_present": dataset.err is not None,
            "var_poisson_present": dataset.var_poisson is not None,
            "var_rnoise_present": dataset.var_rnoise is not None,
            "var_flat_present": dataset.var_flat is not None,
            "dq2_present": dataset.dq2 is not None,
            "flag_dictionary": {
                "source": dictionary.source,
                "package_version": dictionary.package_version,
                "snapshot_matches_installed": dictionary.snapshot_matches_installed,
                "n_flags": len(dictionary.flags),
            },
            "meta": dataset.meta,
            "note": "inspect does not print the science array.",
        }
        print(json.dumps(json_safe(summary), indent=2, sort_keys=True))
    return 0


def cmd_flags(args: argparse.Namespace) -> int:
    with open_dataset(args.image) as dataset:
        if dataset.dq is None:
            raise InvalidDataError(
                "This image has no DQ array. Flag decoding is NOT_EVALUATED, not a clean result."
            )
        col, row = nearest_pixel(args.x, args.y)
        ny, nx = dataset.shape
        if not (0 <= row < ny and 0 <= col < nx):
            raise InvalidDataError(
                f"Pixel x={args.x}, y={args.y} rounds to ({col}, {row}), which is outside shape {dataset.shape}."
            )
        dictionary = load_flag_dictionary()
        decoded = decompose(int(dataset.dq[row, col]), dictionary)
        payload: dict[str, object] = {
            "x": args.x,
            "y": args.y,
            "central_pixel": {"x": col, "y": row},
            "raw_dq": decoded.raw,
            "flags": list(decoded.flags),
            "unknown_bits": list(decoded.unknown_bits),
            "components": [dict(item) for item in decoded.components],
            "science": _finite_or_none(dataset.science[row, col]),
            "flag_dictionary_source": dictionary.source,
        }
        if args.radius_px is not None:
            region = circular_region(dataset.shape, args.x, args.y, args.radius_px, 0.0)
            payload["aperture"] = summarize_region(dataset.dq, region.mask, dictionary)
            payload["aperture_off_image"] = region.n_off_image
        print(json.dumps(json_safe(payload), indent=2, sort_keys=True))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    analyze_files(
        args.image,
        args.catalog,
        args.out,
        settings,
        asserted_level=args.data_level,
        command=" ".join(sys.argv),
    )
    print(f"Wrote {args.out / 'index.html'}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if args.format != "html":
        raise InvalidDataError("v0.1 report rebuild supports --format html")
    rebuild_html(args.directory)
    print(f"Wrote {args.directory / 'index.html'}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        software = report["software"]
        print(f"romanartifactlens {software['romanartifactlens']} on Python {software['python']}")
        for name, info in report["readers"].items():
            state = "available" if info["available"] else "not installed"
            print(f"{name}: {state}. {info['note']}")
        flags = report["flag_dictionary"]
        print(
            f"DQ dictionary: {flags['source']} "
            f"(snapshot match: {flags['snapshot_matches_installed']}, {flags['n_named_flags']} flags)"
        )
        print(report["ngrst_discovery_toolkit"]["note"])
        print(report["network"])
    missing = []
    for requirement in args.require:
        key = "roman_asdf" if requirement == "roman" else requirement
        if not report["readers"][key]["available"]:
            missing.append(requirement)
    if missing:
        raise OptionalDependencyError(
            "Required optional readers are not installed: " + ", ".join(missing)
        )
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    text = explain(args.code)
    if text is None:
        known = ", ".join(sorted(EXPLANATIONS))
        raise InvalidDataError(f"Unknown diagnostic code {args.code}. Known codes: {known}")
    print(f"{args.code}: {text}")
    return 0


def _settings_from_args(args: argparse.Namespace) -> AnalysisSettings:
    return AnalysisSettings(
        aperture_radius_px=args.radius_px,
        annulus_inner_px=getattr(args, "annulus_inner_px", None),
        annulus_outer_px=getattr(args, "annulus_outer_px", None),
        dq_policy=getattr(args, "dq_policy", "exclude_do_not_use"),
        background=getattr(args, "background", "sigma_clip_median"),
        min_background_pixels=getattr(args, "min_background_pixels", 30),
        psf_adapter=getattr(args, "psf", "none"),
        psf_sigma_px=getattr(args, "psf_sigma", None),
        strict=bool(getattr(args, "strict", False)),
    )


def _finite_or_none(value: object) -> float | None:
    import numpy as np

    number = float(value)  # type: ignore[arg-type]
    if not np.isfinite(number):
        return None
    return number


if __name__ == "__main__":
    raise SystemExit(main())
