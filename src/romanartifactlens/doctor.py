"""Report installed readers without downloading reference data."""

from __future__ import annotations

import importlib.util
from typing import Any

from romanartifactlens.dq.definitions import load_flag_dictionary
from romanartifactlens.reports.provenance import software_versions


def doctor_report() -> dict[str, Any]:
    versions = software_versions()
    flags = load_flag_dictionary()
    return {
        "software": versions,
        "readers": {
            "synthetic_npz": {"available": True, "note": "Core reader. Requires declaration SYNTHETIC_TEST."},
            "roman_asdf": {
                "available": versions.get("roman_datamodels") is not None,
                "package": "roman_datamodels",
                "note": "ImageModel is L2. MosaicModel is L3 and is not treated as L2. Generic ASDF is rejected.",
            },
            "stpsf": {
                "available": versions.get("stpsf") is not None,
                "package": "stpsf",
                "note": "Used only with --psf stpsf and filter/detector metadata. Failures are NOT_EVALUATED.",
            },
            "romancal": {
                "available": versions.get("romancal") is not None,
                "note": "Not required. This package does not run the calibration pipeline.",
            },
            "romanisim": {
                "available": versions.get("romanisim") is not None,
                "note": "Not required. Synthetic NPZ fixtures are not romanisim products.",
            },
        },
        "flag_dictionary": {
            "source": flags.source,
            "package_version": flags.package_version,
            "snapshot_matches_installed": flags.snapshot_matches_installed,
            "n_named_flags": len(flags.flags),
        },
        "network": "doctor does not download MAST, CRDS, or STPSF data files.",
        "ngrst_discovery_toolkit": {
            "inspected_repository": False,
            "note": (
                "Plygonality/NGRST-Discovery-Toolkit was not accessible (HTTP 404 for this credential). "
                "Catalogue aliases for label, x_centroid, and y_centroid are implemented and unverified "
                "against the live package."
            ),
        },
    }


def dependency_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None
