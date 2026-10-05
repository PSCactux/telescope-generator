"""Build pipeline: config -> validated meshes -> STL files, plates and summaries."""
from __future__ import annotations

import json
from pathlib import Path

import trimesh

from . import geometry as g
from . import optics
from .config import TelescopeConfig
from .gauges import build_gauges
from .layout import export_plates, pack
from .refractor import DesignError, Dimensions, build_parts, dimensions, sanity_checks, thread_checks


def effective_aperture(cfg: TelescopeConfig, d: Dimensions) -> float:
    """The smallest of the lens clear aperture, the ledge opening and the retainer opening."""
    return min(cfg.objective.clear_aperture, d.aperture, d.retainer_aperture)


def optics_summary(cfg: TelescopeConfig, d: Dimensions) -> dict:
    ap = effective_aperture(cfg, d)
    out = optics.summary(ap, cfg.objective.focal_length, [(e.focal_length, e.apparent_fov) for e in cfg.eyepieces])
    out["nominal_clear_aperture_mm"] = cfg.objective.clear_aperture
    if ap < cfg.objective.clear_aperture:
        out["note"] = (f"the cell openings stop the lens down from {cfg.objective.clear_aperture:g} to {ap:.1f} mm; "
                       "reduce objective.shelf_width to recover aperture")
    return out


def design(cfg: TelescopeConfig) -> tuple[Dimensions, list[dict]]:
    """Derive dimensions and refuse the design if any sanity check fails."""
    d = dimensions(cfg)
    checks = sanity_checks(cfg, d)
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise DesignError("design checks failed:\n  - " + "\n  - ".join(f"{c['check']}: {c['detail']}" for c in failed))
    return d, checks


def build(cfg: TelescopeConfig, out: Path, check_threads: bool = False, log=print) -> dict:
    out = Path(out)
    d, checks = design(cfg)
    parts = build_parts(cfg, d)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    meshes, part_rows, to_pack = {}, [], []
    for p in parts:
        mesh = g.to_mesh(p.name, p.solid)        # raises if not watertight / single body
        mesh.export(out / "parts" / f"{p.name}.stl")
        meshes[p.name] = mesh
        part_rows.append({"name": p.name, "qty": p.qty, "description": p.description,
                          "size_mm": [round(v, 1) for v in mesh.extents], "volume_cm3": round(mesh.volume / 1000, 1),
                          "watertight": bool(mesh.is_watertight)})
        to_pack += [(p.name if p.qty == 1 else f"{p.name}#{k + 1}", mesh) for k in range(p.qty)]
        log(f"  {p.name:<22} x{p.qty}  {mesh.extents[0]:6.1f} x {mesh.extents[1]:6.1f} x {mesh.extents[2]:6.1f} mm  watertight")
    plates = export_plates(pack(to_pack, cfg.printer.bed_x, cfg.printer.bed_y, cfg.printer.max_height), out / "plates")
    summary = {
        "name": cfg.name, "verified_config": cfg.verified, "units": "mm",
        "optics": optics_summary(cfg, d),
        "focus": d.focus,
        "tube_segments_mm": d.segments,
        "parts": part_rows,
        "plates": plates,
        "checks": checks,
        "dimensions": d.as_dict(),
        "config": cfg.to_dict(),
    }
    if check_threads:
        log("  checking threaded pairs (slow)...")
        tc = thread_checks(d, {p.name: p.solid for p in parts})
        summary["thread_checks"] = tc
        bad = [t for t in tc if not t["ok"]]
        if bad:
            raise DesignError(f"thread collision checks failed: {bad}")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")
    (out / "summary.md").write_text(summary_markdown(summary))
    return summary


def summary_markdown(s: dict) -> str:
    o = s["optics"]
    lines = [f"# {s['name']}", ""]
    if not s["verified_config"]:
        lines += ["> This configuration has not been printed and tested. Print the gauges first.", ""]
    lines += ["## Optics", "",
              f"- Effective aperture {o['aperture_mm']} mm (lens {o['nominal_clear_aperture_mm']} mm), focal length {o['focal_length_mm']} mm, f/{o['f_ratio']}",
              f"- Dawes limit {o['dawes_arcsec']}\", Rayleigh limit {o['rayleigh_arcsec']}\"",
              f"- Useful magnification {o['min_useful_magnification']}x to {o['max_useful_magnification']}x, limiting magnitude ~{o['limiting_magnitude']}",
              f"- Light grasp ~{o['light_grasp_vs_eye']}x the naked eye"]
    if "note" in o:
        lines.append(f"- Note: {o['note']}")
    lines += ["", "| Eyepiece | Magnification | Exit pupil | True field |", "|---:|---:|---:|---:|"]
    for e in o["eyepieces"]:
        warn = " (over max useful)" if e["over_max_useful"] else ""
        lines.append(f"| {e['eyepiece_mm']:g} mm | {e['magnification']}x{warn} | {e['exit_pupil_mm']} mm | {e['true_fov_deg']} deg |")
    f = s["focus"]
    lines += ["", "## Focus", "",
              f"Tube segments: {', '.join(f'{x:.0f}' for x in s['tube_segments_mm'])} mm. With the {f['nominal_spacer']:g} mm spacer the "
              f"nominal focus sits inside the focuser travel ({f['margin_inward_mm']} mm towards the objective, "
              f"{f['margin_outward_mm']} mm away). Other spacer combinations reach from {f['all_spacer_combos_range_mm'][0]} "
              f"to +{f['all_spacer_combos_range_mm'][1]} mm around the nominal focus.", "",
              f"Focus test before printing the tubes: with the cell and the eyepiece holder only, the eyepiece shoulder "
              f"should be about {f['focus_test_distance_mm']} mm behind the rear face of the cell when a distant object is sharp. "
              "If you measure something else, put the difference into objective.focal_length and rebuild.", "",
              "## Parts", "", "| Part | Qty | Size (mm) | Description |", "|---|---:|---|---|"]
    for p in s["parts"]:
        lines.append(f"| {p['name']} | {p['qty']} | {' x '.join(f'{v:g}' for v in p['size_mm'])} | {p['description']} |")
    lines += ["", "## Plates", ""]
    for p in s["plates"]:
        lines.append(f"- `{p['file']}` ({p['height_mm']} mm tall): {', '.join(p['parts'])}")
    lines += ["", "## Checks", ""]
    for c in s["checks"]:
        lines.append(f"- [{'x' if c['ok'] else ' '}] {c['check']} ({c['detail']})")
    lines += ["", "Never point a telescope at the Sun without a certified solar filter.", ""]
    return "\n".join(lines)


def build_gauge_set(cfg: TelescopeConfig, out: Path, log=print, **kw) -> dict:
    out = Path(out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    rows, to_pack = [], []
    for gauge in build_gauges(cfg, **kw):
        mesh = g.to_mesh(gauge.name, gauge.solid)
        mesh.export(out / "parts" / f"{gauge.name}.stl")
        rows.append({"name": gauge.name, "description": gauge.description, "size_mm": [round(v, 1) for v in mesh.extents]})
        to_pack.append((gauge.name, mesh))
        log(f"  {gauge.name:<16} {gauge.description}")
    plates = export_plates(pack(to_pack, cfg.printer.bed_x, cfg.printer.bed_y, cfg.printer.max_height), out / "plates", "gauges")
    summary = {"name": cfg.name, "gauges": rows, "plates": plates}
    (out / "gauges.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def load_parts(folder: Path) -> dict[str, trimesh.Trimesh]:
    return {p.stem: trimesh.load_mesh(p) for p in sorted(Path(folder).glob("*.stl"))}
