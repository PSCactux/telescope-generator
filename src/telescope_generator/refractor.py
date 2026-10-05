"""Refractor parts, parametrized from the measurements in the config.

The geometry is the one of the original 70/400 v1 that was printed and confirmed working; every
fixed number of that design is expressed here as an offset from the measured lens bore, the
eyepiece bore and the tube wall, so the 70/400 example reproduces it (within rounding).

Optical frame used for the layout: z axis = optical axis, z = 0 at the flat rear face of the lens
cell, sky towards +z. Parts themselves are exported in print orientation.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass, field

import manifold3d as m
import numpy as np

from . import geometry as g
from .config import TelescopeConfig
from .geometry import EPS, Thread, box, cyl

TH = 12.0                        # axial length of every tube (T) thread
S = Thread(3.6, 0.7, 2.0)        # printed clamp screw: major 8.6, pitch 2
Q = Thread(2.49, 0.686, 1.27)    # 1/4"-20 approximation of the tripod screw
NUT = dict(tan=14.0, axial=12.0, radial=8.0)   # printed square nut for the S screw


class DesignError(ValueError):
    pass


@dataclass
class Dimensions:
    """Every derived number of the design. Saved to summary.json."""
    c: float
    lens_r: float
    aperture: float              # free diameter through the ledge
    retainer_aperture: float
    pocket: float
    T: Thread
    R: Thread
    F: Thread
    tube_r: float
    tube_bore_r: float
    male_bore_r: float
    nose_r: float
    cell: dict
    eyepiece_bore: float
    guide: float
    relief_r: float
    flange_r: float
    flange_h: float
    ring_h: float
    thread_len: float
    travel: float
    pocket_r0: float
    cap_r0: float
    cap_h: float
    cap_pass_r: float
    cap_bore_r: float
    z_focal: float
    z_mouth: float
    chain_nominal: float
    spacers: list
    segments: list               # printed lengths, front (objective side) first
    segment_net: float = 0.0
    cfg_dist_pass: float = 0.0   # distance from the focal plane to the narrow cap opening
    support: dict = field(default_factory=dict)
    dew: dict = field(default_factory=dict)
    focus: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("T", "R", "F"):
            d[k] = {"root": getattr(self, k).root, "depth": getattr(self, k).depth, "pitch": getattr(self, k).pitch,
                    "major_diameter": round(getattr(self, k).major_diameter, 3)}
        return d


def _split_tube(net_total: float, max_len: float) -> list[float]:
    """Split the net tube length into printable segments (each adds length - TH to the chain)."""
    per = max_len - TH
    n = max(1, math.ceil(net_total / per - 1e-9))
    nets = [per] * (n - 1) + [net_total - per * (n - 1)]
    if nets[-1] < 40 and n > 1:              # avoid a stubby last segment: balance them
        nets = [net_total / n] * n
    return [float(round(x + TH)) for x in nets]


def dimensions(cfg: TelescopeConfig) -> Dimensions:
    o, e = cfg.objective, cfg.eyepiece_holder
    c = cfg.fit.thread_clearance
    lens_r = cfg.cell_bore / 2
    R = Thread(round(lens_r + 1.075, 3), 1.05, 3.0)      # retainer thread, 45 deg flanks
    T = Thread(round(lens_r + 3.475, 3), 1.4, 4.0)       # tube joint thread
    tube_bore_r = T.root + T.depth
    tube_r = tube_bore_r + cfg.tube.wall_thickness
    aperture = cfg.cell_bore - 2 * o.shelf_width
    pocket = o.edge_thickness + 1.5

    z_fem = TH
    r_cone0 = T.root + c + T.depth + 0.25                 # starts outside the female thread: no step
    z_cone_end = z_fem + (r_cone0 - aperture / 2)         # 45 deg baffle cone down to the aperture
    z_pocket = z_cone_end + 3                             # 3 mm ledge, the glass sits on it
    z_thread = z_pocket + pocket
    cell = dict(z_fem=z_fem, r_cone0=r_cone0, z_cone_end=z_cone_end, z_pocket=z_pocket, z_thread=z_thread,
                top=z_thread + 12, lens_mid=z_pocket + o.edge_thickness / 2)

    bore = cfg.eyepiece_bore
    r = bore / 2
    relief_r = r + 0.55
    F = Thread(round(relief_r + 4.5, 3), 1.0, 3.0)        # focuser thread
    flange_r = F.root + 7
    ring_h = 12.0
    travel = e.focus_travel
    cap_r0 = F.root + c + F.depth + 4.75
    if tube_r < cap_r0 + 8:
        raise DesignError(f"the tube ({2 * tube_r:.0f} mm) is too narrow for a {e.barrel_diameter} mm eyepiece focuser "
                          f"(needs at least {2 * (cap_r0 + 8):.0f} mm); this layout suits lenses of about 55 mm and up")
    cap_h = (tube_r - cap_r0) + 6
    cap_pass_r = F.root + F.depth + c + 0.35
    male_bore_r = T.root - 2.1
    cap_bore_r = min(male_bore_r, cap_pass_r + cap_h - ring_h - 0.1)

    z_focal = cell["lens_mid"] - o.focal_length
    z_mouth = z_focal - e.field_stop_depth                # eyepiece shoulder on the holder mouth
    flange_h = 15.0
    z_cap_outer = z_mouth + flange_h + travel / 2          # holder at mid travel
    chain = -(z_cap_outer + cap_h)                         # cell rear face -> cap shoulder
    spacers = [float(s) for s in cfg.tube.focus_spacers]
    net_total = chain - spacers[0]
    if net_total < 2 * TH + 10:
        raise DesignError(f"focal length {o.focal_length} mm is too short for this layout: the tube would be "
                          f"{net_total:.0f} mm; you need a longer focal length or a different focuser")
    segments = _split_tube(net_total, cfg.tube.max_segment_length)

    ring_in = tube_r + 0.2
    ring_out = ring_in + 5
    support = dict(ring_in=ring_in, ring_out=ring_out, ring_w=45.0, foot=(42.0, 45.0, 8.0), z_axis=8 + 6 + ring_in,
                   ear_x0=ring_out - 19.2, ear_x1=ring_out + 18.8, top_ear_x0=ring_out - 11.2, shank=30.0)
    support["screw_x"] = support["ear_x1"] - 8

    dew_r_in = tube_r + cfg.fit.slip_clearance
    dew = dict(r_in=dew_r_in, r_out=dew_r_in + 2.4, sleeve=15.0, r_stop=R.root + c + R.depth + 0.5,
               length=cfg.accessories.dew_shield_length)

    d = Dimensions(c=c, lens_r=lens_r, aperture=aperture, retainer_aperture=aperture - 1.0, pocket=pocket, T=T, R=R, F=F,
                   tube_r=tube_r, tube_bore_r=tube_bore_r, male_bore_r=male_bore_r, nose_r=lens_r - 0.125, cell=cell,
                   eyepiece_bore=bore, guide=e.insertion_length - 2, relief_r=relief_r, flange_r=flange_r, flange_h=flange_h,
                   ring_h=ring_h, thread_len=travel + ring_h, travel=travel, pocket_r0=r + 1.55, cap_r0=cap_r0, cap_h=cap_h,
                   cap_pass_r=cap_pass_r, cap_bore_r=cap_bore_r, z_focal=z_focal, z_mouth=z_mouth, chain_nominal=chain,
                   spacers=spacers, segments=segments, segment_net=net_total, support=support, dew=dew)
    d.cfg_dist_pass = e.field_stop_depth + flange_h + travel / 2 + ring_h
    d.focus = focus_coverage(d)
    return d


def focus_coverage(d: Dimensions) -> dict:
    """Where the focal plane can be reached with the real (rounded) segment lengths."""
    tubes_net = sum(s - TH for s in d.segments)
    out = {}
    for k in range(len(d.spacers) + 1):
        for combo in itertools.combinations(d.spacers, k):
            shoulder = -(tubes_net + sum(combo))
            cap_outer = shoulder - d.cap_h
            # mouth range: holder screwed fully in .. fully out
            out[combo] = (cap_outer - d.flange_h - d.travel, cap_outer - d.flange_h)
    nominal = out[(d.spacers[0],)]
    lo = min(v[0] for v in out.values())
    hi = max(v[1] for v in out.values())
    return {"mouth_needed_z": round(d.z_mouth, 2),
            "focus_test_distance_mm": round(-d.z_mouth, 1),   # cell rear face -> eyepiece shoulder, nominal
            "nominal_spacer": d.spacers[0],
            "nominal_mouth_range_z": [round(nominal[0], 2), round(nominal[1], 2)],
            "covered_with_nominal_spacer": nominal[0] <= d.z_mouth <= nominal[1],
            "margin_outward_mm": round(d.z_mouth - nominal[0], 2),
            "margin_inward_mm": round(nominal[1] - d.z_mouth, 2),
            "all_spacer_combos_range_mm": [round(lo - d.z_mouth, 1), round(hi - d.z_mouth, 1)]}


def sanity_checks(cfg: TelescopeConfig, d: Dimensions) -> list[dict]:
    """Dimension checks. Each is {'check', 'ok', 'detail'}; build refuses to continue if any fails."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add("cell bore = gauge fit or measured + 2 x clearance", abs(2 * d.lens_r - cfg.cell_bore) < 1e-9, f"{2 * d.lens_r:.2f} mm")
    add("glass pocket deeper than the edge thickness", d.pocket >= cfg.objective.edge_thickness + 1, f"{d.pocket:.1f} >= {cfg.objective.edge_thickness} + 1")
    add("retainer nose fits in the pocket", 2 * d.nose_r < 2 * d.lens_r - 0.2, f"{2 * d.nose_r:.2f} < {2 * d.lens_r - 0.2:.2f}")
    add("ledge supports the glass edge", d.aperture < 2 * d.lens_r - 2, f"aperture {d.aperture:.2f}")
    for glass in (cfg.objective.edge_thickness - 1.5, cfg.objective.edge_thickness + 1.5):
        engaged = d.cell["top"] - (d.cell["z_pocket"] + glass + 3)
        add(f"retainer thread engaged with {glass:.1f} mm of glass", engaged >= 6, f"{engaged:.1f} mm")
    add("cell wall outside the female T thread >= 1.5 mm", d.tube_r - (d.T.root + d.c + d.T.depth) >= 1.5,
        f"{d.tube_r - (d.T.root + d.c + d.T.depth):.2f} mm")
    add("eyepiece bore larger than the barrel", d.eyepiece_bore > cfg.eyepiece_holder.barrel_diameter,
        f"{d.eyepiece_bore:.2f} > {cfg.eyepiece_holder.barrel_diameter}")
    add("guide shorter than the barrel (eyepiece rests on its shoulder)", d.guide < cfg.eyepiece_holder.insertion_length,
        f"{d.guide:.1f} < {cfg.eyepiece_holder.insertion_length}")
    add("printed nut fits in the holder flange", NUT["radial"] + d.pocket_r0 + 2 <= d.flange_r, f"{NUT['radial'] + d.pocket_r0 + 2:.2f} <= {d.flange_r:.2f}")
    add("holder thread passes through the cap", d.cap_pass_r > d.F.root + d.F.depth + 0.3, f"{2 * d.cap_pass_r:.2f} > {d.F.major_diameter:.2f}")
    add("cap cone is taller than its F ring", d.cap_h > d.ring_h + 2, f"{d.cap_h:.1f} > {d.ring_h + 2}")
    add("focus travel covers the focal plane with the nominal spacer", d.focus["covered_with_nominal_spacer"],
        f"{d.focus['margin_inward_mm']} mm towards the objective, {d.focus['margin_outward_mm']} mm away")
    beam = _beam_diameter(cfg, d, d.cfg_dist_pass)
    add("light beam clears the focuser cap opening", 2 * d.cap_pass_r > beam + 1, f"opening {2 * d.cap_pass_r:.1f} vs beam {beam:.1f}")
    for i, s in enumerate(d.segments):
        add(f"tube segment {i + 1} printable", 2 * TH + 4 < s <= cfg.printer.max_height, f"{s:.0f} mm")
    ear_bottom = d.support["z_axis"] - 14 - (d.support["ear_x1"] - d.support["ear_x0"])
    add("support gusset above the bed", ear_bottom > -10, f"{ear_bottom:.1f}")
    dw = d.dew
    min_dew = dw["sleeve"] + 2 * (dw["r_in"] - dw["r_stop"]) + 1.5 + 5
    if cfg.accessories.dew_shield_length > 0:
        add("dew shield long enough for its sleeve and stop", dw["length"] >= min_dew, f"{dw['length']} >= {min_dew:.1f}")
    return checks


def _beam_diameter(cfg: TelescopeConfig, d: Dimensions, dist: float) -> float:
    """Diameter of the light bundle at `dist` mm in front of the focal plane, for a fully
    illuminated field as wide as the eyepiece bore minus 4 mm (a generous field stop)."""
    f = cfg.objective.focal_length
    field = d.eyepiece_bore - 4
    return d.aperture * dist / f + field * (1 - dist / f)


# ---------------------------------------------------------------------------------------------
# Parts (print orientation)
# ---------------------------------------------------------------------------------------------

def t_male(d: Dimensions, h: float = TH) -> m.Manifold:
    return g.thread_solid(d.T, h, fade=True)


def t_female_cut(d: Dimensions, z0: float, h: float = TH) -> m.Manifold:
    """Female T cut ending exactly at z0 + h (never overlap a cylinder of intermediate radius: slivers)."""
    return g.thread_solid(d.T, h + 1, clearance=d.c).translate((0, 0, z0 - 1))


def lens_cell(d: Dimensions) -> m.Manifold:
    L = d.cell
    body = cyl(d.tube_r, L["top"])
    body -= g.thread_solid(d.T, L["z_fem"] + 1, clearance=d.c).translate((0, 0, -1))
    body -= cyl(L["r_cone0"], L["z_cone_end"] - L["z_fem"], L["z_fem"], d.aperture / 2)
    body -= cyl(d.aperture / 2, L["z_pocket"] - L["z_cone_end"] + 1, L["z_cone_end"] - EPS)
    body -= cyl(d.lens_r, d.pocket + EPS, L["z_pocket"])
    body -= cyl(d.lens_r + 0.35, 0.35 + EPS, L["z_pocket"] - EPS)          # clean corner on the ledge
    body -= g.thread_solid(d.R, 12 + 2, clearance=d.c).translate((0, 0, L["z_thread"] - 1))
    return body


def lens_retainer(d: Dimensions) -> m.Manifold:
    """Printed with the notched face down; the nose (up) presses the glass edge through a soft ring."""
    ret_h, nose_h = 10.0, 3.0
    body = g.thread_solid(d.R, ret_h, fade=True) + cyl(d.nose_r, nose_h, ret_h)
    body -= cyl(d.retainer_aperture / 2, ret_h + nose_h + 2, -1)
    for k in range(4):
        body -= m.Manifold.cube((12, 4, 3.5)).translate((d.nose_r - 6.5, -2, -1)).rotate((0, 0, 90 * k))
    return body


def tube_segment(d: Dimensions, length: float) -> m.Manifold:
    """Female T at the bottom (flat on the bed), male T on top, flat shoulder under the male."""
    body = cyl(d.tube_r, length - TH) + t_male(d).translate((0, 0, length - TH))
    body -= t_female_cut(d, 0)
    body -= cyl(d.tube_bore_r, length - TH - 3.5 - TH, TH)
    body -= cyl(d.tube_bore_r, 3.5 + EPS, length - TH - 3.5, d.male_bore_r)  # 45 deg towards the male
    body -= cyl(d.male_bore_r, TH + 2, length - TH - EPS)
    return body


def focus_spacer(d: Dimensions, net: float) -> m.Manifold:
    e = net - TH
    body = cyl(d.tube_r, TH + e) + t_male(d).translate((0, 0, TH + e))
    body -= t_female_cut(d, 0)
    r0 = d.T.root + d.c + d.T.depth + 0.25            # just outside the female thread: no step
    cone = r0 - d.male_bore_r
    if e < cone - 0.5:
        raise DesignError(f"spacer {net:g} mm is too short: it needs at least {TH + cone - 0.5:.1f} mm")
    body -= cyl(r0, cone, TH, d.male_bore_r)                # 45 deg cone down to the male bore
    body -= cyl(d.male_bore_r, TH + e + TH + 2, TH + cone - EPS)
    return body


def focuser_cap(d: Dimensions) -> m.Manifold:
    """Female F ring at the bottom, conical body, flat shoulder and male T on top."""
    cone_h = d.tube_r - d.cap_r0
    body = cyl(d.cap_r0, cone_h, 0, d.tube_r) + cyl(d.tube_r, d.cap_h - cone_h, cone_h) + t_male(d).translate((0, 0, d.cap_h))
    body -= g.thread_solid(d.F, d.ring_h + 1, clearance=d.c).translate((0, 0, -1))
    body -= cyl(d.cap_pass_r, d.cap_h - d.ring_h, d.ring_h, d.cap_bore_r)     # 45 deg baffle cone
    body -= cyl(d.cap_bore_r, TH + 2, d.cap_h - EPS)
    return body


def eyepiece_holder(d: Dimensions) -> m.Manifold:
    """Helical focuser: grip flange (mouth down) + male F thread. Turning it moves the eyepiece."""
    fh = d.flange_h
    body = cyl(d.flange_r, fh) + g.thread_solid(d.F, d.thread_len, fade=True).translate((0, 0, fh))
    for k in range(8):
        body -= cyl(2.5, fh + 2, -1).translate((d.flange_r, 0, 0)).rotate((0, 0, 45 * k))
    r = d.eyepiece_bore / 2
    total = fh + d.thread_len
    hole = cyl(r, d.guide + 1, -1)
    hole += cyl(r + 0.7, 0.7 + EPS, -EPS, r)                 # lead-in chamfer at the mouth
    hole += cyl(r + 0.35, 0.35 + EPS, -EPS)                   # elephant-foot relief
    hole += cyl(d.relief_r, total - d.guide + 1, d.guide)     # the barrel tip never bottoms out
    body -= hole
    pocket = m.Manifold.cube((NUT["radial"] + 0.4, NUT["tan"] + 0.4, NUT["axial"] + 1.4)).translate(
        (d.pocket_r0 - 0.2, -(NUT["tan"] + 0.4) / 2, -1))
    bore = m.Manifold.cylinder(d.flange_r + 2, S.root + S.depth + 0.4, S.root + S.depth + 0.4, 64).rotate((0, 90, 0)).translate((r - 1, 0, 6.2))
    body -= (pocket + bore).rotate((0, 0, 22.5))
    return body


def clamp_screw(shank: float = 16.0) -> m.Manifold:
    head = cyl(8, 5)
    for k in range(8):
        head -= cyl(1.5, 7, -1).translate((8, 0, 0)).rotate((0, 0, 45 * k))
    body = g.thread_solid(S, shank, fade=True).translate((0, 0, 5))
    tip = cyl(S.root - 0.3, 2, 5 + shank, S.root - 1.0)
    return head + body + tip


def clamp_nut(c: float) -> m.Manifold:
    block = m.Manifold.cube((NUT["tan"], NUT["axial"], NUT["radial"])).translate((-NUT["tan"] / 2, -NUT["axial"] / 2, 0))
    block -= g.thread_solid(S, NUT["radial"] + 2, clearance=c).translate((0, 0, -1))
    if c >= 0.30:  # identification grooves for the looser nut
        for sgn in (1, -1):
            block -= m.Manifold.cube((1.2, NUT["axial"] + 2, 0.8)).translate((sgn * 5.5 - 0.6, -NUT["axial"] / 2 - 1, NUT["radial"] - 0.8))
    return block


def mount_cradle(cfg: TelescopeConfig, d: Dimensions) -> m.Manifold:
    """Lower half ring with a flat foot for the tripod head and slots for the printed nuts."""
    sp = d.support
    half_w = sp["ring_w"] / 2
    z_axis, ring_in, ring_out = sp["z_axis"], sp["ring_in"], sp["ring_out"]
    ear_low = (z_axis - 14, z_axis)
    x0, x1 = sp["ear_x0"], sp["ear_x1"]
    n = g.SEGMENTS
    tube = m.Manifold.cylinder(sp["ring_w"] + 2, ring_in, ring_in, n).rotate((90, 0, 0)).translate((0, half_w + 1, z_axis))
    ring = m.Manifold.cylinder(sp["ring_w"], ring_out, ring_out, n).rotate((90, 0, 0)).translate((0, half_w, z_axis))
    ring -= box(-200, 200, -100, 100, z_axis, z_axis + 200)
    bw = ring_out * 0.7317
    block = box(-bw, bw, -half_w, half_w, 0, z_axis - ring_out * np.cos(np.pi / 4) + 0.5)
    fx, fy, fz = sp["foot"]
    body = ring + block + box(-fx / 2, fx / 2, -fy / 2, fy / 2, 0, fz)
    slot_w, slot_h = NUT["axial"] + 0.4, NUT["radial"] + 0.6
    gusset_bottom = max(0.5, ear_low[0] - (x1 - x0))
    for sgn in (1, -1):
        ear = box(min(sgn * x0, sgn * x1), max(sgn * x0, sgn * x1), -half_w, half_w, ear_low[0], ear_low[1])
        gusset = m.CrossSection([[(x0, gusset_bottom), (x1, ear_low[0] + 0.1), (x0, ear_low[0] + 0.1)]]).extrude(sp["ring_w"])
        gusset = gusset.rotate((90, 0, 0)).translate((0, half_w, 0))
        if sgn < 0:
            gusset = gusset.mirror((1, 0, 0))
        body += ear + gusset
        rr = S.root + S.depth + 0.4
        body -= m.Manifold.cylinder(40, rr, rr, 64).translate((sgn * sp["screw_x"], 0, ear_low[1] - 39))
        body -= box(sgn * sp["screw_x"] - slot_w / 2, sgn * sp["screw_x"] + slot_w / 2, -half_w - 1, half_w + 1,
                    ear_low[1] - 2.8 - slot_h, ear_low[1] - 2.8)
    body -= tube
    tr = cfg.tripod
    if tr.mode == "printed_thread":
        body -= g.thread_solid(Q, 8, clearance=tr.thread_clearance).translate((0, 0, -1))   # blind, 7 mm deep
    else:
        floor = 1.2
        af = tr.nut_across_flats + 0.3
        h = tr.nut_thickness + 0.3
        hexa = m.CrossSection.circle(af / 2 / math.cos(math.pi / 6), 6).rotate(30).extrude(h).translate((0, 0, floor))
        slot = box(-af / 2, af / 2, -half_w - 1, 0, floor, floor + h)
        body -= hexa + slot + cyl(3.4, floor + 2, -1)
    return body


def mount_clamp(d: Dimensions) -> m.Manifold:
    """Upper half ring, printed lying down (arc in XY, tube axis along z)."""
    sp = d.support
    y0 = 1.0
    ring = cyl(sp["ring_out"], sp["ring_w"]) - box(-200, 200, -200, 0, -1, sp["ring_w"] + 1)
    ears = box(sp["top_ear_x0"], sp["ear_x1"], y0, y0 + 14, 0, sp["ring_w"]) + box(-sp["ear_x1"], -sp["top_ear_x0"], y0, y0 + 14, 0, sp["ring_w"])
    body = ring + ears - cyl(sp["ring_in"], sp["ring_w"] + 2, -1)
    rr = S.root + S.depth + 0.4
    for sgn in (1, -1):
        body -= m.Manifold.cylinder(30, rr, rr, 64).rotate((-90, 0, 0)).translate((sgn * sp["screw_x"], -1, sp["ring_w"] / 2))
    return body


def dew_shield(d: Dimensions) -> m.Manifold:
    """Slips over the front of the cell and rests on its front face. Printed sleeve-down."""
    w = d.dew
    r_in, r_stop, sl, L = w["r_in"], w["r_stop"], w["sleeve"], w["length"]
    dr = r_in - r_stop
    hole = cyl(r_in, sl + 1 + EPS, -1)
    hole += cyl(r_in, dr, sl, r_stop)                          # 45 deg inward stop (no overhang beyond 45)
    hole += cyl(r_stop, 1.5 + 2 * EPS, sl + dr - EPS)
    hole += cyl(r_stop, dr, sl + dr + 1.5, r_in)
    hole += cyl(r_in, L, sl + 2 * dr + 1.5 - EPS)
    return cyl(w["r_out"], L) - hole


def dust_cap(cfg: TelescopeConfig, d: Dimensions) -> m.Manifold:
    """Slip-on cap for the front of the dew shield (or of the cell if there is no shield)."""
    r_target = d.dew["r_out"] if cfg.accessories.dew_shield_length > 0 else d.tube_r
    r_in = r_target + cfg.fit.slip_clearance
    return cyl(r_in + 2, 12) - cyl(r_in, 12, 2)


@dataclass
class Part:
    name: str
    solid: m.Manifold
    qty: int
    description: str


def build_parts(cfg: TelescopeConfig, d: Dimensions) -> list[Part]:
    c = cfg.fit.thread_clearance
    parts = [
        Part("lens_cell", lens_cell(d), 1, f"lens cell, glass pocket {2 * d.lens_r:.2f} x {d.pocket:.1f} mm, female T at the rear"),
        Part("lens_retainer", lens_retainer(d), 1, "threaded retainer ring; use a soft ring between it and the glass"),
    ]
    for i, length in enumerate(d.segments):
        parts.append(Part(f"tube_{i + 1}", tube_segment(d, length), 1, f"tube segment {i + 1} ({length:.0f} mm), counted from the objective"))
    for s in dict.fromkeys(d.spacers):
        parts.append(Part(f"spacer_{s:g}", focus_spacer(d, s), 1, f"focus spacer, net extension {s:g} mm"))
    parts += [
        Part("focuser_cap", focuser_cap(d), 1, "rear cap: female F (focuser) below, male T above"),
        Part("eyepiece_holder", eyepiece_holder(d), 1, f"helical focuser, bore {d.eyepiece_bore:.2f}, travel {d.travel:g} mm"),
        Part("eyepiece_screw", clamp_screw(16), 1, "printed thumb screw that holds the eyepiece"),
        Part(f"eyepiece_nut_c{round(c * 100):02d}", clamp_nut(c), 1, "printed nut for the thumb screw"),
        Part(f"eyepiece_nut_c{round((c + 0.1) * 100):02d}", clamp_nut(c + 0.1), 1, "looser spare nut (grooved)"),
        Part("mount_cradle", mount_cradle(cfg, d), 1, "tube cradle with tripod foot (" +
             ("printed 1/4\"-20 thread" if cfg.tripod.mode == "printed_thread" else "1/4\"-20 hex nut pocket, slide the nut in from the side") + ")"),
        Part("mount_clamp", mount_clamp(d), 1, "upper half ring of the mount"),
        Part("mount_screw", clamp_screw(d.support["shank"]), 2, "printed screws that close the mount"),
        Part(f"mount_nut_c{round(c * 100):02d}", clamp_nut(c), 2, "printed nuts for the mount, slide into the cradle ears"),
    ]
    if cfg.accessories.dew_shield_length > 0:
        parts.append(Part("dew_shield", dew_shield(d), 1, f"dew shield, {d.dew['length']:g} mm"))
    if cfg.accessories.dust_cap:
        parts.append(Part("dust_cap", dust_cap(cfg, d), 1, "slip-on dust cap"))
    return parts


def thread_checks(d: Dimensions, parts: dict[str, m.Manifold], step: int = 10) -> list[dict]:
    """Collision tests of the threaded pairs (slow): one free rotation exists, a wrong one collides."""
    res = []
    probe = g.thread_solid(d.T, TH, fade=True)
    ring_T = g.female_ring(d.T, TH, d.tube_r + 1, d.c)

    def rec(name, items):
        for it in items:
            res.append({"pair": name, **it})

    rec("cell female T / male T", g.thread_fit_check(probe, lambda p, a: parts["lens_cell"].rotate((0, 0, a)).translate((0, 0, p)), (0, 5), step))
    t1 = parts["tube_1"]
    L1 = d.segments[0]
    rec("tube_1 male T / female T", g.thread_fit_check(t1, lambda p, a: ring_T.rotate((0, 0, a)).translate((0, 0, L1 - TH + p)), (0, 5), step))
    cap = parts["focuser_cap"]
    rec("eyepiece holder / cap F", g.thread_fit_check(parts["eyepiece_holder"], lambda p, a: cap.rotate((0, 0, a)).translate((0, 0, d.flange_h + p)),
                                                     (0, d.travel / 2, d.travel), step))
    ret = parts["lens_retainer"]

    def place_ret(pos, ang):
        flipped = ret.rotate((180, 0, 0)).translate((0, 0, 13))
        return flipped.rotate((0, 0, ang)).translate((0, 0, d.cell["z_pocket"] + pos))
    return res + [{"pair": "cell / retainer", **it} for it in g.thread_fit_check(parts["lens_cell"], place_ret, (d.pocket - 1.5,), step)]
