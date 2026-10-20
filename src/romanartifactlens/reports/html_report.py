"""Self-contained HTML evidence pages."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

from romanartifactlens.reports.figures import legend_note


def write_candidate_html(
    path: Path,
    report: dict[str, Any],
    figure_paths: dict[str, str],
    manifest: dict[str, Any],
) -> None:
    directory = path.parent
    images = []
    for key, filename in figure_paths.items():
        if not filename.endswith(".png"):
            continue
        images.append((key, _embed(directory / filename), filename))
    evidence_rows = "\n".join(_evidence_row(item) for item in report["evidence"])
    limitations = "".join(f"<li>{html.escape(text)}</li>" for text in report["limitations"])
    not_concluded = "".join(f"<li>{html.escape(text)}</li>" for text in report["not_concluded"])
    banner = _banner(report)
    position = report["position"]
    measurements = report["measurements"]
    background = measurements["background"]
    uncertainty = measurements["uncertainty"]
    morphology = measurements["morphology"]
    central = report["dq_summary"].get("central") or {}
    flags = ", ".join(central.get("flags") or []) or "none"
    unknown = ", ".join(str(bit) for bit in (central.get("unknown_bits") or [])) or "none"
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>RomanArtifactLens {html.escape(str(report["candidate_id"]))}</title>
<style>
:root {{
  --paper: #f6f1e7;
  --ink: #221c16;
  --rule: #d5cbbd;
  --review: #8a4b08;
  --ok: #1d4a38;
  --gap: #6e4b16;
  --banner: #f3d48a;
}}
body {{ margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.45 "Iowan Old Style", Palatino, Georgia, serif; }}
main {{ max-width: 980px; margin: 0 auto; padding: 28px 22px 64px; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.2rem; }}
h2 {{ font-size: 1.15rem; margin-top: 1.6rem; border-top: 1px solid var(--rule); padding-top: 0.7rem; }}
.banner {{ background: var(--banner); border: 1px solid #c4a15a; padding: 10px 12px; margin: 12px 0 18px; }}
.status {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-family: ui-monospace, monospace; font-size: 0.85rem; }}
.REVIEW_RECOMMENDED {{ background: #f3d7b0; color: var(--review); }}
.NO_FLAGGED_CONCERNS_IN_AVAILABLE_CHECKS {{ background: #d5eadf; color: var(--ok); }}
.INSUFFICIENT_EVIDENCE {{ background: #efe1c2; color: var(--gap); }}
.kind {{ font-family: ui-monospace, monospace; font-size: 0.78rem; }}
table {{ border-collapse: collapse; width: 100%; background: #fffdf8; }}
th, td {{ border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; padding: 6px 8px; }}
th {{ font-size: 0.82rem; }}
figure {{ margin: 0 0 14px; }}
img {{ max-width: 100%; height: auto; background: white; }}
figcaption {{ font-size: 0.85rem; color: #4a433a; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.86rem; }}
</style>
</head>
<body>
<main>
<p>RomanArtifactLens {html.escape(str(manifest.get("software", {}).get("romanartifactlens", "")))}</p>
<h1>{html.escape(str(report["candidate_id"]))}</h1>
<p>Status <span class="status {html.escape(str(report["overall_review_status"]))}">{html.escape(str(report["overall_review_status"]))}</span></p>
{banner}
<p>Level <code>{html.escape(str(report["dataset_level"]))}</code>
· kind <code>{html.escape(str(report["dataset_kind"]))}</code>
· units <code>{html.escape(str(report["units"]))}</code></p>
<p>{html.escape(str(report["units_note"]))}</p>
<h2>Position</h2>
<p>x = <code>{_fmt(position.get("x"))}</code>, y = <code>{_fmt(position.get("y"))}</code>,
ra = <code>{_fmt(position.get("ra_deg"))}</code>, dec = <code>{_fmt(position.get("dec_deg"))}</code>,
edge distance = <code>{_fmt(position.get("edge_distance_px"))}</code> px.</p>
<p>{html.escape(str(position.get("coordinate_convention")))}</p>
<h2>Cutouts</h2>
<p>{html.escape(legend_note())}</p>
<div class="grid">
{"".join(_figure(title, src) for title, src, _name in images)}
</div>
<h2>DQ at the central pixel</h2>
<p>Raw value <code>{html.escape(str(central.get("raw")))}</code>.
Named flags: <code>{html.escape(flags)}</code>.
Unknown bits: <code>{html.escape(unknown)}</code>.</p>
<h2>Local measurements</h2>
<ul>
<li>Background {html.escape(str(background.get("status")))}: value {_fmt(background.get("value"))}, scale {_fmt(background.get("scale"))}, n_used {html.escape(str(background.get("n_used")))} ({html.escape(str(background.get("method")))}).</li>
<li>Uncertainty {html.escape(str(uncertainty.get("status")))}: {html.escape(str(uncertainty.get("reason")))}. Ratio {_fmt(uncertainty.get("significance"))}.</li>
<li>Morphology {html.escape(str(morphology.get("status")))}: area {_fmt(morphology.get("area_px"))}, axis ratio {_fmt(morphology.get("axis_ratio"))}, concentration {_fmt(morphology.get("central_concentration"))}. Method {html.escape(str(morphology.get("method")))}.</li>
</ul>
<h2>Evidence</h2>
<table>
<thead><tr><th>Code</th><th>Kind</th><th>Status</th><th>Value</th><th>What was measured</th><th>What it does not conclude</th></tr></thead>
<tbody>
{evidence_rows}
</tbody>
</table>
<h2>What this packet does not conclude</h2>
<ul>{not_concluded}</ul>
<h2>Limitations</h2>
<ul>{limitations}</ul>
<h2>Provenance</h2>
<p>Command <code>{html.escape(str(manifest.get("command", "")))}</code></p>
<p>Created {html.escape(str(manifest.get("created_utc", "")))}.
Flag source <code>{html.escape(str(manifest.get("flag_definitions", {}).get("source", "")))}</code>.</p>
</main>
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def write_index_html(path: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    body_rows = "\n".join(_index_row(row) for row in rows)
    limitations = "".join(f"<li>{html.escape(text)}</li>" for text in manifest.get("limitations", []))
    banner = ""
    if manifest.get("dataset_kind") == "SYNTHETIC_TEST":
        banner = (
            "<div class='banner'><strong>SYNTHETIC_TEST.</strong> "
            "These cutouts were generated by RomanArtifactLens. They are not Roman observations "
            "and they are not calibrated flight data.</div>"
        )
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>RomanArtifactLens evidence index</title>
<style>
body {{ margin: 0; background: #f6f1e7; color: #221c16; font: 16px/1.45 Palatino, Georgia, serif; }}
main {{ max-width: 980px; margin: 0 auto; padding: 28px 22px 64px; }}
table {{ border-collapse: collapse; width: 100%; background: #fffdf8; }}
th, td {{ border-bottom: 1px solid #d5cbbd; text-align: left; padding: 6px 8px; vertical-align: top; }}
.banner {{ background: #f3d48a; border: 1px solid #c4a15a; padding: 10px 12px; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.86rem; }}
a {{ color: #6d2c1a; }}
</style>
</head>
<body>
<main>
<h1>Candidate evidence index</h1>
{banner}
<p>{html.escape(str(manifest.get("dataset_kind")))} · level {html.escape(str(manifest.get("data_level")))}
· units {html.escape(str(manifest.get("units")))}</p>
<p>Command <code>{html.escape(str(manifest.get("command", "")))}</code></p>
<p>Seed <code>{html.escape(str(manifest.get("seed")))}</code></p>
<h2>Candidates</h2>
<table>
<thead><tr><th>Candidate</th><th>Status</th><th>Central flags</th><th>Aperture DO_NOT_USE</th><th>Significance</th><th>Packet</th></tr></thead>
<tbody>
{body_rows}
</tbody>
</table>
<h2>Dataset limitations</h2>
<ul>{limitations}</ul>
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _figure(title: str, src: str) -> str:
    return (
        f"<figure><img alt='{html.escape(title)}' src='{src}'/>"
        f"<figcaption>{html.escape(title)}</figcaption></figure>"
    )


def _evidence_row(item: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><code>{html.escape(str(item['code']))}</code></td>"
        f"<td class='kind'>{html.escape(str(item['kind']))}</td>"
        f"<td>{html.escape(str(item['status']))}</td>"
        f"<td>{html.escape(_fmt(item.get('value')))}</td>"
        f"<td>{html.escape(str(item['description']))}</td>"
        f"<td>{html.escape(str(item['interpretation']))}</td>"
        "</tr>"
    )


def _index_row(row: dict[str, Any]) -> str:
    link = html.escape(str(row["href"]))
    return (
        "<tr>"
        f"<td><code>{html.escape(str(row['candidate_id']))}</code></td>"
        f"<td>{html.escape(str(row['overall_review_status']))}</td>"
        f"<td>{html.escape(str(row['central_flags']))}</td>"
        f"<td>{html.escape(str(row['do_not_use_fraction']))}</td>"
        f"<td>{html.escape(str(row['significance']))}</td>"
        f"<td><a href='{link}'>review</a></td>"
        "</tr>"
    )


def _banner(report: dict[str, Any]) -> str:
    if report["dataset_kind"] == "SYNTHETIC_TEST":
        return (
            "<div class='banner'><strong>SYNTHETIC_TEST.</strong> "
            "The numbers in this packet come from a labelled fixture. "
            "They are not a Roman observation and not a calibrated detector artefact.</div>"
        )
    if report["dataset_kind"] == "ROMAN_L3":
        return (
            "<div class='banner'><strong>L3 mosaic.</strong> "
            "Missing per-pixel DQ is not treated as a clean image. "
            "L2 flag meanings are not assumed.</div>"
        )
    return (
        "<div class='banner'>Roman datamodel opened with roman_datamodels. "
        "Review the manifest for whether this file is flight data or a simulation, "
        "and for the unit string actually attached to the array.</div>"
    )


def _embed(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
