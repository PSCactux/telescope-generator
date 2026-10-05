"""Command line: telescope-generator {validate,gauges,build,preview} <config.json>"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import ConfigError, load_config
from .geometry import MeshError
from .refractor import DesignError

SUN_WARNING = "Never point a telescope at the Sun without a proper certified solar filter."


def _optics_lines(s: dict) -> list[str]:
    o = s["optics"]
    lines = [f"Optics: aperture {o['aperture_mm']:g} mm, focal {o['focal_length_mm']:g} mm, f/{o['f_ratio']}, "
             f"Dawes {o['dawes_arcsec']}\", Rayleigh {o['rayleigh_arcsec']}\", max useful {o['max_useful_magnification']}x, "
             f"limiting magnitude ~{o['limiting_magnitude']}"]
    for e in o["eyepieces"]:
        lines.append(f"  {e['eyepiece_mm']:>4g} mm eyepiece: {e['magnification']:>5g}x  true field {e['true_fov_deg']} deg  exit pupil {e['exit_pupil_mm']} mm"
                     + ("  (over max useful)" if e["over_max_useful"] else ""))
    if "note" in o:
        lines.append(f"  note: {o['note']}")
    return lines


def cmd_validate(args) -> int:
    from .build import design, optics_summary
    cfg = load_config(args.config)
    d, checks = design(cfg)
    for c in checks:
        print(f"  ok  {c['check']} ({c['detail']})")
    print("\n".join(_optics_lines({"optics": optics_summary(cfg, d)})))
    print(f"Configuration is valid. Tube segments: {', '.join(f'{s:.0f}' for s in d.segments)} mm")
    return 0


def cmd_gauges(args) -> int:
    from .build import build_gauge_set
    cfg = load_config(args.config)
    out = Path(args.out)
    print(f"Fit-test gauges for '{cfg.name}' -> {out}")
    s = build_gauge_set(cfg, out, lens_step=args.lens_step, lens_count=args.lens_count, threads=not args.no_threads)
    for p in s["plates"]:
        print(f"  plate {p['file']}: {', '.join(p['parts'])}")
    if args.preview:
        from .build import load_parts
        from .preview import render_grid
        path = render_grid(list(load_parts(out / "parts").items()), out / "gauges.png", f"{cfg.name}: fit-test gauges")
        print(f"  preview {path}")
    print("Print these first, test them against your real lens, eyepiece and tripod, then write the sizes that fit into the config.")
    return 0


def cmd_build(args) -> int:
    from .build import build
    cfg = load_config(args.config)
    out = Path(args.out)
    t0 = time.time()
    print(f"Building '{cfg.name}' -> {out}")
    if not cfg.verified:
        print("  warning: this configuration is marked as unverified (never printed)")
    s = build(cfg, out, check_threads=args.check_threads)
    print(f"{len(s['parts'])} parts, {len(s['plates'])} plates, all meshes watertight, {len(s['checks'])} design checks passed "
          f"({time.time() - t0:.1f} s)")
    for p in s["plates"]:
        print(f"  plates/{p['file']} ({p['height_mm']} mm tall): {', '.join(p['parts'])}")
    print("\n".join(_optics_lines(s)))
    f = s["focus"]
    print(f"Focus: nominal focal plane reached with the {f['nominal_spacer']:g} mm spacer at mid travel "
          f"(+{f['margin_inward_mm']} / -{f['margin_outward_mm']} mm of travel left)")
    print(f"Summary: {out / 'summary.md'}")
    print(SUN_WARNING)
    return 0


def cmd_preview(args) -> int:
    from .preview import render_assembly, render_hero, render_parts
    cfg = load_config(args.config)
    out = Path(args.out)
    print(render_hero(cfg, out / "telescope.png", resolution=args.resolution))
    print(render_assembly(cfg, out / "assembly.png", resolution=args.resolution))
    print(render_parts(cfg, out / "parts.png", resolution=args.resolution))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="telescope-generator", description="Generate a 3D-printable refractor from your measurements.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate", help="check a config and print the optics")
    p.add_argument("config")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("gauges", help="generate fit-test gauges (print these first)")
    p.add_argument("config")
    p.add_argument("--out", default="gauges")
    p.add_argument("--lens-step", type=float, default=0.25, help="diameter step of the lens rings (mm)")
    p.add_argument("--lens-count", type=int, default=5, help="number of lens rings")
    p.add_argument("--no-threads", action="store_true", help="skip the thread test sets")
    p.add_argument("--preview", action="store_true", help="also render gauges.png")
    p.set_defaults(func=cmd_gauges)
    p = sub.add_parser("build", help="generate all telescope parts as STL")
    p.add_argument("config")
    p.add_argument("--out", default="out")
    p.add_argument("--check-threads", action="store_true", help="also run thread collision tests (slow)")
    p.set_defaults(func=cmd_build)
    p = sub.add_parser("preview", help="render PNG views of the assembly and the parts")
    p.add_argument("config")
    p.add_argument("--out", default="out")
    p.add_argument("--resolution", type=int, default=96, help="circle segments used for the render")
    p.set_defaults(func=cmd_preview)
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, DesignError, MeshError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
