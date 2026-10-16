"""Software versions and input hashes for the manifest."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from romanartifactlens import __version__
from romanartifactlens.jsonutil import sha256_file


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def software_versions() -> dict[str, str | None]:
    names = (
        "numpy",
        "scipy",
        "astropy",
        "matplotlib",
        "photutils",
        "roman_datamodels",
        "asdf",
        "gwcs",
        "stpsf",
        "romancal",
        "romanisim",
    )
    payload: dict[str, str | None] = {
        "romanartifactlens": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for name in names:
        payload[name] = package_version(name)
    return payload


def file_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
