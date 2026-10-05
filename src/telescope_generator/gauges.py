"""Fit-test gauges: print these small parts first and pick the size that fits your real parts.

- L rings: thin rings (2 mm tall) around the expected lens/cell diameter. Pick the smallest that
  passes around the glass edge without pressure; put its bore in objective.gauge_fit_diameter.
- O bushings: 16 mm tall bores for the eyepiece barrel. Pick the smallest that slides by hand
  without wobble; put it in eyepiece_holder.gauge_fit_bore.
- T and F threads: one male and three females (0.15 / 0.25 / 0.35 mm radial clearance) of the tube
  joint and focuser threads, light versions (2.5 turns). Pick the smallest that turns smoothly;
  put it in fit.thread_clearance.
- P nuts: printed 1/4"-20 nuts for the tripod screw (only for tripod.mode = printed_thread).
"""
from __future__ import annotations

from dataclasses import dataclass

import manifold3d as m

from . import geometry as g
from .config import TelescopeConfig
from .geometry import EPS, Thread, cyl
from .refractor import Q, dimensions

THREAD_CLEARANCES = (0.15, 0.25, 0.35)


@dataclass
class Gauge:
    name: str
    solid: m.Manifold
    description: str


def lens_ring(diameter: float) -> m.Manifold:
    """2 mm tall ring; between z = 0.2 and 1.7 the wall has the nominal diameter."""
    r = diameter / 2
    hole = cyl(r, 4, -1)
    hole += cyl(r + 0.22, 0.22, -0.02, r)       # first-layer relief
    hole += cyl(r, 0.32, 1.7, r + 0.32)         # lead-in
    return g.label_tab(cyl(r + 2, 2) - hole, r + 2, f"L {diameter:.2f}", h=1.2)


def bore_bushing(diameter: float, height: float = 16) -> m.Manifold:
    r = diameter / 2
    outer = r + 4
    hole = cyl(r, height + 2, -1)
    hole += cyl(r, 0.7 + EPS, height - 0.7, r + 0.7 + EPS)
    hole += cyl(r + 0.35, 0.35 + EPS, -EPS, r)
    return g.label_tab(cyl(outer, height) - hole, outer, f"O {diameter:.2f}")


def thread_set(prefix: str, t: Thread, h: float, inner_wall: float) -> list[Gauge]:
    """Light thread test set: a hollow male and three females with different clearance."""
    outer = t.root + t.depth + 2.0
    flange = 3.0
    male = cyl(outer, flange) + g.thread_solid(t, h, fade=True).translate((0, 0, flange))
    male -= cyl(t.root - inner_wall, flange + h + 2, -1)
    out = [Gauge(f"{prefix}_male", g.label_tab(male, outer, f"{prefix} M"), f"{prefix} thread male")]
    for c in THREAD_CLEARANCES:
        fem = g.label_tab(g.female_ring(t, h, outer, c), outer, f"{prefix} {c:.2f}")
        out.append(Gauge(f"{prefix}_female_c{round(c * 100):02d}", fem, f"{prefix} thread female, radial clearance {c}"))
    return out


def tripod_nut(c: float) -> m.Manifold:
    body = cyl(10, 6)
    for k in range(12):
        body -= cyl(1.2, 8, -1).translate((10, 0, 0)).rotate((0, 0, 30 * k))
    body -= g.thread_solid(Q, 8, clearance=c).translate((0, 0, -1))
    return g.label_tab(body, 10, f"P {c:.2f}")


def series(center: float, step: float, count: int) -> list[float]:
    half = (count - 1) / 2
    return [round(center + (k - half) * step, 2) for k in range(count)]


def build_gauges(cfg: TelescopeConfig, lens_step: float = 0.25, lens_count: int = 5,
                 eyepiece_step: float = 0.2, eyepiece_count: int = 3, threads: bool = True) -> list[Gauge]:
    out: list[Gauge] = []
    for dia in series(cfg.cell_bore, lens_step, lens_count):
        out.append(Gauge(f"L_{dia:.2f}", lens_ring(dia), f"lens ring, bore {dia:.2f}"))
    barrel = cfg.eyepiece_holder.barrel_diameter
    for k in range(eyepiece_count):
        dia = round(barrel + 0.15 + k * eyepiece_step, 2)
        out.append(Gauge(f"O_{dia:.2f}", bore_bushing(dia), f"eyepiece bushing, bore {dia:.2f}"))
    if threads:
        d = dimensions(cfg)
        out += thread_set("T", d.T, 10.0, 2.1)
        out += thread_set("F", d.F, 7.5, 2.25)
    if cfg.tripod.mode == "printed_thread":
        for c in THREAD_CLEARANCES:
            out.append(Gauge(f"P_c{round(c * 100):02d}", tripod_nut(c), f"tripod 1/4\"-20 printed nut, clearance {c}"))
    return out
