"""Configuration: the measurements you took, as a JSON file, loaded into dataclasses and validated.

Every length is in millimetres. See examples/refractor-70-400.json for a complete file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised with every problem found, one per line."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("invalid configuration:\n  - " + "\n  - ".join(problems))


@dataclass
class Objective:
    clear_aperture: float                     # nominal aperture of the lens, e.g. 70
    focal_length: float                       # nominal focal length, e.g. 400
    edge_thickness: float                     # thickness of the whole lens (or doublet) at its edge
    gauge_fit_diameter: float | None = None   # bore of the printed test ring that fitted best
    measured_diameter: float | None = None    # caliper reading of the glass / metal cell (used if no gauge)
    radial_clearance: float = 0.15            # added per side to measured_diameter only
    shelf_width: float = 2.6                  # radial width of the ledge the glass rests on


@dataclass
class EyepieceHolder:
    barrel_diameter: float = 31.75            # nominal barrel: 31.75 (1.25") or 50.8 (2")
    gauge_fit_bore: float | None = None       # bore of the printed test bushing that slid best
    radial_clearance: float = 0.075           # added per side to barrel_diameter if no gauge
    insertion_length: float = 20.0            # barrel length from its tip to the eyepiece shoulder
    field_stop_depth: float = 6.0             # assumed field stop position inside the barrel, from the shoulder
    focus_travel: float = 18.0                # helical focuser travel


@dataclass
class Eyepiece:
    focal_length: float
    apparent_fov: float = 50.0                # degrees; check your eyepiece data sheet


@dataclass
class Tube:
    wall_thickness: float = 3.0
    max_segment_length: float = 200.0         # printed standing up: keep under the printer height
    focus_spacers: list[float] = field(default_factory=lambda: [16.0, 20.0, 30.0])  # net extensions; first = nominal


@dataclass
class Fit:
    thread_clearance: float = 0.25            # radial clearance of every printed thread (pick it with the gauges)
    slip_clearance: float = 0.25              # radial clearance of slip fits (dew shield, dust cap)


@dataclass
class Accessories:
    dew_shield_length: float = 100.0
    dust_cap: bool = True


@dataclass
class Tripod:
    mode: str = "printed_thread"              # "printed_thread" (1/4"-20 printed in the foot) or "nut_pocket"
    thread_clearance: float = 0.25            # for printed_thread
    screw_protrusion: float = 5.0             # how far the tripod screw sticks out of its platform
    nut_across_flats: float = 11.11           # 7/16" hex nut for 1/4"-20
    nut_thickness: float = 5.6


@dataclass
class Printer:
    bed_x: float = 256.0
    bed_y: float = 256.0
    max_height: float = 250.0


@dataclass
class TelescopeConfig:
    name: str
    objective: Objective
    eyepiece_holder: EyepieceHolder
    eyepieces: list[Eyepiece]
    tube: Tube = field(default_factory=Tube)
    fit: Fit = field(default_factory=Fit)
    accessories: Accessories = field(default_factory=Accessories)
    tripod: Tripod = field(default_factory=Tripod)
    printer: Printer = field(default_factory=Printer)
    verified: bool = False                    # True only if this exact config was printed and used
    notes: str = ""

    # --- derived values -------------------------------------------------------------
    @property
    def cell_bore(self) -> float:
        """Diameter of the pocket that holds the glass."""
        o = self.objective
        if o.gauge_fit_diameter is not None:
            return float(o.gauge_fit_diameter)
        return float(o.measured_diameter) + 2 * o.radial_clearance

    @property
    def eyepiece_bore(self) -> float:
        e = self.eyepiece_holder
        if e.gauge_fit_bore is not None:
            return float(e.gauge_fit_bore)
        return e.barrel_diameter + 2 * e.radial_clearance

    def to_dict(self) -> dict:
        return asdict(self)


def _build(cls, data: Any, path: str, problems: list[str]):
    """Instantiate a dataclass from a dict, reporting unknown and missing keys."""
    if not isinstance(data, dict):
        problems.append(f"{path}: expected an object")
        return None
    known = {f.name: f for f in fields(cls)}
    for key in data:
        if key not in known and not key.startswith("_"):
            problems.append(f"{path}.{key}: unknown key")
    kwargs = {}
    sub = {"objective": Objective, "eyepiece_holder": EyepieceHolder, "tube": Tube, "fit": Fit,
           "accessories": Accessories, "tripod": Tripod, "printer": Printer}
    for name in known:
        if name not in data:
            continue
        value = data[name]
        if cls is TelescopeConfig and name in sub:
            value = _build(sub[name], value, f"{path}.{name}", problems)
        elif cls is TelescopeConfig and name == "eyepieces":
            value = [_build(Eyepiece, v, f"{path}.eyepieces[{i}]", problems) for i, v in enumerate(value or [])]
        kwargs[name] = value
    try:
        return cls(**kwargs)
    except TypeError as exc:
        problems.append(f"{path}: {exc}")
        return None


def _num(problems, label, value, lo=None, hi=None, allow_none=False):
    if value is None and allow_none:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{label}: must be a number, got {value!r}")
        return False
    if lo is not None and value < lo:
        problems.append(f"{label}: {value} is below the minimum {lo}")
        return False
    if hi is not None and value > hi:
        problems.append(f"{label}: {value} is above the maximum {hi}")
        return False
    return True


def validate(cfg: TelescopeConfig) -> list[str]:
    """Return the list of problems (empty if the config is buildable)."""
    p: list[str] = []
    o, e, t = cfg.objective, cfg.eyepiece_holder, cfg.tube
    _num(p, "objective.clear_aperture", o.clear_aperture, 20, 160)
    _num(p, "objective.focal_length", o.focal_length, 100, 2000)
    _num(p, "objective.edge_thickness", o.edge_thickness, 1, 40)
    _num(p, "objective.gauge_fit_diameter", o.gauge_fit_diameter, 20, 170, allow_none=True)
    _num(p, "objective.measured_diameter", o.measured_diameter, 20, 170, allow_none=True)
    _num(p, "objective.radial_clearance", o.radial_clearance, 0, 1)
    _num(p, "objective.shelf_width", o.shelf_width, 0.8, 6)
    if o.gauge_fit_diameter is None and o.measured_diameter is None:
        p.append("objective: give gauge_fit_diameter (printed ring that fitted) or measured_diameter (caliper)")
    _num(p, "eyepiece_holder.barrel_diameter", e.barrel_diameter, 20, 60)
    _num(p, "eyepiece_holder.gauge_fit_bore", e.gauge_fit_bore, 20, 62, allow_none=True)
    _num(p, "eyepiece_holder.insertion_length", e.insertion_length, 10, 60)
    _num(p, "eyepiece_holder.field_stop_depth", e.field_stop_depth, -30, 40)
    _num(p, "eyepiece_holder.focus_travel", e.focus_travel, 8, 40)
    if not cfg.eyepieces:
        p.append("eyepieces: list at least one eyepiece")
    for i, ep in enumerate(cfg.eyepieces):
        if ep is not None:
            _num(p, f"eyepieces[{i}].focal_length", ep.focal_length, 2, 60)
            _num(p, f"eyepieces[{i}].apparent_fov", ep.apparent_fov, 20, 120)
    _num(p, "tube.wall_thickness", t.wall_thickness, 1.6, 8)
    _num(p, "tube.max_segment_length", t.max_segment_length, 60, 400)
    if not t.focus_spacers:
        p.append("tube.focus_spacers: give at least one spacer (the first one is the nominal)")
    for s in t.focus_spacers:
        _num(p, "tube.focus_spacers", s, 16, 80)
    _num(p, "fit.thread_clearance", cfg.fit.thread_clearance, 0.05, 0.6)
    _num(p, "fit.slip_clearance", cfg.fit.slip_clearance, 0.05, 1)
    _num(p, "accessories.dew_shield_length", cfg.accessories.dew_shield_length, 0, 300)
    tr = cfg.tripod
    if tr.mode not in ("printed_thread", "nut_pocket"):
        p.append(f"tripod.mode: must be 'printed_thread' or 'nut_pocket', got {tr.mode!r}")
    _num(p, "tripod.thread_clearance", tr.thread_clearance, 0.05, 0.6)
    _num(p, "tripod.screw_protrusion", tr.screw_protrusion, 3, 15)
    pr = cfg.printer
    _num(p, "printer.bed_x", pr.bed_x, 120, 1000)
    _num(p, "printer.bed_y", pr.bed_y, 120, 1000)
    _num(p, "printer.max_height", pr.max_height, 100, 1000)
    if p:
        return p  # cross checks below need valid numbers

    # --- cross checks: physically impossible or inconsistent combinations
    if cfg.cell_bore < o.clear_aperture:
        p.append(f"objective: cell bore {cfg.cell_bore:.2f} is smaller than the clear aperture {o.clear_aperture}; "
                 "the lens cannot be smaller than its own aperture")
    if cfg.cell_bore - 2 * o.shelf_width < 0.85 * o.clear_aperture:
        p.append("objective.shelf_width: the ledge would hide more than 15 % of the aperture")
    if cfg.eyepiece_bore <= e.barrel_diameter:
        p.append(f"eyepiece_holder: bore {cfg.eyepiece_bore:.2f} must be larger than the barrel {e.barrel_diameter}")
    if cfg.eyepiece_bore > e.barrel_diameter + 1.5:
        p.append(f"eyepiece_holder: bore {cfg.eyepiece_bore:.2f} is >1.5 mm over the barrel; the eyepiece would wobble")
    if not 0 < e.field_stop_depth < e.insertion_length:
        p.append("eyepiece_holder.field_stop_depth must lie inside the barrel (0 < depth < insertion_length)")
    if o.focal_length / o.clear_aperture < 3:
        p.append(f"objective: f/{o.focal_length / o.clear_aperture:.1f} is faster than f/3; not a realistic achromat")
    if t.max_segment_length > pr.max_height:
        p.append(f"tube.max_segment_length {t.max_segment_length} exceeds printer.max_height {pr.max_height}")
    if cfg.accessories.dew_shield_length > pr.max_height:
        p.append("accessories.dew_shield_length exceeds printer.max_height")
    if tr.mode == "nut_pocket" and tr.screw_protrusion < 1.0 + tr.nut_thickness * 0.5:
        p.append("tripod.screw_protrusion is too short to engage a nut through a 1 mm floor")
    return p


def load_config(path: str | Path) -> TelescopeConfig:
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise ConfigError([f"{path}: file not found"]) from None
    except json.JSONDecodeError as exc:
        raise ConfigError([f"{path}: invalid JSON ({exc})"]) from None
    return config_from_dict(data)


def config_from_dict(data: dict) -> TelescopeConfig:
    problems: list[str] = []
    for key in ("name", "objective", "eyepiece_holder", "eyepieces"):
        if key not in data:
            problems.append(f"{key}: required")
    if problems:
        raise ConfigError(problems)
    cfg = _build(TelescopeConfig, data, "config", problems)
    if problems:
        raise ConfigError(problems)
    problems = validate(cfg)
    if problems:
        raise ConfigError(problems)
    return cfg

