"""PNG cutouts. Display images are separate from the numeric cutout."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt
import numpy as np

from romanartifactlens.evidence.evaluate import CandidatePacket


def write_candidate_figures(packet: CandidatePacket, directory: Path, units: str | None) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    unit_label = units or "array unit not attached"
    science_path = directory / "cutout_science.png"
    _science_png(packet, science_path, unit_label)
    paths["cutout_science"] = science_path.name
    display_path = directory / "cutout_display_dq.png"
    _display_png(packet, display_path)
    paths["cutout_display_dq"] = display_path.name
    if packet.cutout.err is not None:
        err_path = directory / "cutout_uncertainty.png"
        _err_png(packet, err_path, unit_label)
        paths["cutout_uncertainty"] = err_path.name
    if packet.psf_residual is not None:
        resid_path = directory / "cutout_psf_residual.png"
        _residual_png(packet, resid_path, unit_label)
        paths["cutout_psf_residual"] = resid_path.name
    np.save(directory / "cutout_science.npy", packet.cutout.science)
    _write_csv(directory / "cutout_science.csv", packet.cutout.science)
    paths["cutout_science_npy"] = "cutout_science.npy"
    paths["cutout_science_csv"] = "cutout_science.csv"
    return paths


def _science_png(packet: CandidatePacket, path: Path, unit_label: str) -> None:
    science = packet.cutout.science
    finite = science[np.isfinite(science)]
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    if finite.size:
        vmin = float(np.percentile(finite, 1))
        vmax = float(np.percentile(finite, 99))
        if vmax <= vmin:
            vmin = float(np.min(finite))
            vmax = float(np.max(finite))
    else:
        vmin, vmax = 0.0, 1.0
    image = ax.imshow(science, origin="lower", cmap="cividis", vmin=vmin, vmax=vmax)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label(unit_label)
    ax.set_title("Science cutout (colour scale only)")
    ax.set_xlabel("cutout column")
    ax.set_ylabel("cutout row")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _display_png(packet: CandidatePacket, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    ax.imshow(packet.display, origin="lower", cmap="gray", vmin=0, vmax=1)
    overlay = _dq_overlay(packet)
    if overlay is not None:
        ax.imshow(overlay, origin="lower", interpolation="nearest")
    ax.set_title("Asinh display and DQ overlay")
    ax.set_xlabel("cutout column")
    ax.set_ylabel("cutout row")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _err_png(packet: CandidatePacket, path: Path, unit_label: str) -> None:
    err = packet.cutout.err
    assert err is not None
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    finite = err[np.isfinite(err)]
    vmax = float(np.percentile(finite, 99)) if finite.size else 1.0
    image = ax.imshow(err, origin="lower", cmap="magma", vmin=0, vmax=max(vmax, 1e-6))
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label(unit_label)
    ax.set_title("Uncertainty cutout")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _residual_png(packet: CandidatePacket, path: Path, unit_label: str) -> None:
    residual = packet.psf_residual
    assert residual is not None
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    finite = residual[np.isfinite(residual)]
    limit = float(np.percentile(np.abs(finite), 99)) if finite.size else 1.0
    image = ax.imshow(residual, origin="lower", cmap="coolwarm", vmin=-limit, vmax=limit)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label(unit_label + " residual")
    ax.set_title("PSF residual (see model label)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _dq_overlay(packet: CandidatePacket) -> np.ndarray | None:
    dq = packet.cutout.dq
    if dq is None:
        return None
    coverage = packet.cutout.coverage
    rgba = np.zeros(dq.shape + (4,), dtype=np.float64)
    layers = (
        (np.uint32(1), (0.72, 0.12, 0.10, 0.55)),
        (np.uint32(4), (0.90, 0.45, 0.05, 0.45)),
        (np.uint32(2), (0.85, 0.75, 0.10, 0.40)),
    )
    painted = np.zeros(dq.shape, dtype=bool)
    for bit, colour in layers:
        hit = coverage & ((dq & bit) != 0)
        rgba[hit] = colour
        painted |= hit
    other = coverage & (dq != 0) & ~painted
    rgba[other] = (0.35, 0.25, 0.55, 0.40)
    if not np.any(rgba[..., 3] > 0):
        return None
    return rgba


def _write_csv(path: Path, science: np.ndarray) -> None:
    np.savetxt(path, science, delimiter=",", fmt="%.8g")


def legend_note() -> str:
    return (
        "DQ overlay: red DO_NOT_USE, orange JUMP_DET, gold SATURATED, purple any other non-zero bit. "
        "Off-image samples are blank, not zero-DQ."
    )
