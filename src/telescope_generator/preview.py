"""Matplotlib previews: the assembled telescope (3D + longitudinal section) and every part.

These are renders of the real generated meshes, at a lower circle resolution for speed.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.expanduser("~"), ".cache", "telescope-generator-mpl"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from . import geometry as g
from .build import design, optics_summary
from .config import TelescopeConfig
from .refractor import TH, build_parts

BG = "#f3f5f8"
INK = "#1d3040"
MUTED = "#465866"
COLORS = {"lens_cell": "#4e8098", "lens_retainer": "#7aa6bd", "glass": "#8fd3f4", "tube": "#7f8c99", "spacer": "#a0b7a8",
          "focuser_cap": "#65957c", "eyepiece_holder": "#c48a51", "eyepiece": "#333a44", "mount": "#8a6f4e",
          "dew_shield": "#5d6b78", "other": "#9a7fb0"}


def _color(name: str) -> str:
    for prefix, key in (("tube_", "tube"), ("spacer_", "spacer"), ("mount", "mount")):
        if name.startswith(prefix):
            return COLORS[key]
    for key, col in COLORS.items():
        if name.startswith(key):
            return col
    return COLORS["other"]


def shade(mesh: trimesh.Trimesh, color: str, alpha: float = 1.0, tris=None) -> np.ndarray:
    light = np.array([-0.4, -0.5, 0.77])
    light /= np.linalg.norm(light)
    normals = mesh.face_normals if tris is None else trimesh.triangles.normals(tris)[0]
    b = 0.45 + 0.55 * np.clip(normals @ light, 0, 1)
    rgb = np.array(matplotlib.colors.to_rgb(color))
    return np.column_stack((b[:, None] * rgb[None, :], np.full(len(b), alpha)))


def _rot(matrix_cols) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = np.array(matrix_cols, dtype=float).T
    return t


def assemble(cfg: TelescopeConfig, meshes: dict[str, trimesh.Trimesh], d) -> list[tuple[str, trimesh.Trimesh, str, float]]:
    """Place the parts in telescope coordinates: z = optical axis, z = 0 at the rear face of the cell."""
    out = []
    cell = meshes["lens_cell"].copy()
    out.append(("lens_cell", cell, COLORS["lens_cell"], 1.0))
    ret = meshes["lens_retainer"].copy()
    ret.apply_transform(trimesh.transformations.rotation_matrix(np.pi, (1, 0, 0)))
    ret.apply_translation((0, 0, d.cell["z_pocket"] + cfg.objective.edge_thickness - ret.bounds[0, 2]))
    out.append(("lens_retainer", ret, COLORS["lens_retainer"], 1.0))
    glass = trimesh.creation.cylinder(d.lens_r - 0.2, cfg.objective.edge_thickness, sections=96)
    glass.apply_translation((0, 0, d.cell["z_pocket"] + cfg.objective.edge_thickness / 2))
    out.append(("glass", glass, COLORS["glass"], 0.55))
    if "dew_shield" in meshes:
        dew = meshes["dew_shield"].copy()
        dew.apply_translation((0, 0, d.cell["top"] - d.dew["sleeve"]))
        out.append(("dew_shield", dew, COLORS["dew_shield"], 1.0))
    z = TH  # the male of each piece goes into the female of the previous one
    chain = [f"tube_{i + 1}" for i in range(len(d.segments))] + [f"spacer_{d.spacers[0]:g}", "focuser_cap"]
    for name in chain:
        mesh = meshes[name].copy()
        mesh.apply_translation((0, 0, z - mesh.bounds[1, 2]))
        out.append((name, mesh, _color(name), 1.0))
        z = mesh.bounds[0, 2] + TH
    cap_bottom = z - TH
    mouth = cap_bottom - d.flange_h - d.travel / 2
    holder = meshes["eyepiece_holder"].copy()
    holder.apply_translation((0, 0, mouth))
    out.append(("eyepiece_holder", holder, COLORS["eyepiece_holder"], 1.0))
    eh = cfg.eyepiece_holder
    barrel = trimesh.creation.cylinder(eh.barrel_diameter / 2, eh.insertion_length, sections=64)
    barrel.apply_translation((0, 0, mouth + eh.insertion_length / 2))
    body = trimesh.creation.cylinder(eh.barrel_diameter / 2 + 1.5, 25, sections=64)
    body.apply_translation((0, 0, mouth - 12.5))
    out.append(("eyepiece_barrel", barrel, "#9aa3ad", 1.0))
    out.append(("eyepiece_body", body, COLORS["eyepiece"], 1.0))
    # Mount roughly at the middle of the tube. Cradle print frame: tube axis along y, up = +z.
    zc = cap_bottom / 2
    sp = d.support
    cradle = meshes["mount_cradle"].copy()
    cradle.apply_transform(_rot([(0, -1, 0), (0, 0, 1), (-1, 0, 0)]))       # x->-y, y->z, z->-x
    cradle.apply_translation((sp["z_axis"], 0, zc))
    out.append(("mount_cradle", cradle, COLORS["mount"], 1.0))
    clamp = meshes["mount_clamp"].copy()                                       # arc in XY, axis along z
    clamp.apply_transform(_rot([(0, 1, 0), (-1, 0, 0), (0, 0, 1)]))         # x->y, y->-x, z->z
    clamp.apply_translation((0, 0, zc - sp["ring_w"] / 2))
    out.append(("mount_clamp", clamp, "#b08d62", 1.0))
    return out


def _view3d(ax, parts, zlim=None, horizontal=True, elev=18, azim=-70, zoom=1.0):
    """Shaded triangles; with horizontal=True the optical axis runs along the screen."""
    for _, mesh, color, alpha in parts:
        tris = mesh.triangles
        cols = shade(mesh, color, alpha)
        if zlim is not None:
            keep = (mesh.triangles_center[:, 2] > zlim[0]) & (mesh.triangles_center[:, 2] < zlim[1])
            tris, cols = tris[keep], cols[keep]
        if horizontal:  # optical axis along the screen x: (x, y, z) -> (z, y, -x)
            tris = np.stack((tris[..., 2], tris[..., 1], -tris[..., 0]), axis=-1)
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    allb = np.vstack([p[1].bounds for p in parts])
    lo, hi = (allb[:, 2].min(), allb[:, 2].max()) if zlim is None else zlim
    r = max(np.abs(allb[:, :2]).max(), 50)
    if horizontal:
        ax.set_xlim(lo, hi); ax.set_ylim(-r, r); ax.set_zlim(-r, r)
        ax.set_box_aspect((hi - lo, 2 * r, 2 * r), zoom=zoom)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def _section(ax, parts, zlim, d, focal_z):
    """Cut through the plane y = 0; optical axis drawn horizontally."""
    for name, mesh, color, alpha in parts:
        sec = mesh.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0))
        if sec is None:
            continue
        planar, T = sec.to_2D()
        for poly in planar.polygons_full:
            for ring, fill in [(poly.exterior, color)] + [(h, BG) for h in poly.interiors]:
                xy = np.array(ring.coords)
                pts = trimesh.transform_points(np.column_stack((xy, np.zeros(len(xy)))), T)
                ax.add_patch(Polygon(np.column_stack((pts[:, 2], -pts[:, 0])), closed=True, color=fill,
                                     alpha=alpha if fill != BG else 1, lw=0))
    ax.axvline(focal_z, color="#b03030", lw=0.9, ls="--")
    ax.set_xlim(*zlim)
    ax.set_ylim(-d.tube_r - 22, d.tube_r + 22)
    ax.set_aspect("equal")
    ax.set_axis_off()


def _meshes(cfg: TelescopeConfig, resolution: int):
    old = g.SEGMENTS
    g.set_resolution(resolution)
    try:
        d, _ = design(cfg)
        return d, {p.name: g.to_mesh(p.name, p.solid) for p in build_parts(cfg, d)}
    finally:
        g.set_resolution(old)


def _render3d_image(parts, elev=20, azim=-58, size_px=1800, pad=12) -> np.ndarray:
    """3D axes keep a square box, so a long telescope ends up small. Render it in a square
    figure and crop the image to its content instead."""
    fig = plt.figure(figsize=(size_px / 100, size_px / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1), projection="3d", proj_type="ortho")
    ax.set_facecolor(BG)
    _view3d(ax, parts, elev=elev, azim=azim, zoom=1.0)
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    bg = (np.array(matplotlib.colors.to_rgb(BG)) * 255).astype(int)
    mask = np.abs(img.astype(int) - bg).max(axis=2) > 8
    rows, cols = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    r0, r1 = max(rows[0] - pad, 0), min(rows[-1] + pad, img.shape[0])
    c0, c1 = max(cols[0] - pad, 0), min(cols[-1] + pad, img.shape[1])
    return img[r0:r1, c0:c1]


def render_hero(cfg: TelescopeConfig, path: Path, resolution: int = 96) -> Path:
    """3D view of the assembled telescope only, cropped (used at the top of the README)."""
    d, meshes = _meshes(cfg, resolution)
    img = _render3d_image(assemble(cfg, meshes, d), size_px=2000, pad=30)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(path, img)
    return path


def render_assembly(cfg: TelescopeConfig, path: Path, resolution: int = 96) -> Path:
    d, meshes = _meshes(cfg, resolution)
    parts = assemble(cfg, meshes, d)
    tube_parts = [p for p in parts if not p[0].startswith("mount")]
    opt = optics_summary(cfg, d)
    zmin = min(p[1].bounds[0, 2] for p in parts) - 10
    zmax = max(p[1].bounds[1, 2] for p in parts) + 10

    fig = plt.figure(figsize=(16, 11), facecolor=BG)
    gs = fig.add_gridspec(3, 3, height_ratios=(1.0, 0.75, 1.0))
    ax = fig.add_subplot(gs[0, :])
    ax.imshow(_render3d_image(parts, elev=16, azim=-62))
    ax.set_axis_off()
    ax.set_title("Assembled, objective on the right (generated meshes)", color=INK, fontsize=12)
    ax = fig.add_subplot(gs[1, :])
    ax.set_facecolor(BG)
    _section(ax, tube_parts, (zmin, zmax), d, d.z_focal)
    ax.set_title(f"Longitudinal section, {d.spacers[0]:g} mm spacer, focuser at mid travel (dashed: nominal focal plane)",
                 color=INK, fontsize=11)
    ax = fig.add_subplot(gs[2, 0])
    ax.set_facecolor(BG)
    _section(ax, tube_parts, (-30, d.cell["top"] + 40), d, d.z_focal)
    ax.set_title("Objective end: cell, glass, retainer, dew shield", color=INK, fontsize=10)
    ax = fig.add_subplot(gs[2, 1])
    ax.set_facecolor(BG)
    holder = next(p for p in parts if p[0] == "eyepiece_holder")[1]
    z0 = holder.bounds[0, 2]
    _section(ax, tube_parts, (z0 - 35, z0 + 110), d, d.z_focal)
    ax.set_title("Focuser: helical holder threads into the cap", color=INK, fontsize=10)
    ax = fig.add_subplot(gs[2, 2])
    ax.set_axis_off()
    lines = [f"Aperture {opt['aperture_mm']:g} mm  ·  focal {opt['focal_length_mm']:g} mm  ·  f/{opt['f_ratio']}",
             f"Dawes {opt['dawes_arcsec']}\"  ·  Rayleigh {opt['rayleigh_arcsec']}\"",
             f"Max useful {opt['max_useful_magnification']}x  ·  limiting mag ~{opt['limiting_magnitude']}", ""]
    for e in opt["eyepieces"]:
        lines.append(f"{e['eyepiece_mm']:g} mm eyepiece: {e['magnification']:g}x, field {e['true_fov_deg']} deg, pupil {e['exit_pupil_mm']} mm")
    lines += ["", f"Tube segments: {' + '.join(f'{s:.0f}' for s in d.segments)} mm",
              f"Overall length ~{zmax - zmin - 20:.0f} mm (with eyepiece)"]
    ax.text(0.0, 0.95, "\n".join(lines), va="top", ha="left", fontsize=10.5, color=INK, family="DejaVu Sans Mono",
            transform=ax.transAxes)
    fig.suptitle(cfg.name, fontsize=20, weight="bold", color=INK, y=0.985)
    fig.text(0.5, 0.012, "All dimensions in mm. Never point a telescope at the Sun without a certified solar filter.",
             ha="center", fontsize=10, color=MUTED)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.94, wspace=0.05, hspace=0.12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor=BG)
    plt.close(fig)
    return path


def render_grid(meshes: list[tuple[str, trimesh.Trimesh]], path: Path, title: str, cols: int = 5) -> Path:
    rows = int(np.ceil(len(meshes) / cols))
    fig = plt.figure(figsize=(3.2 * cols, 3.2 * rows + 0.8), facecolor=BG)
    for i, (name, mesh) in enumerate(meshes):
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d", proj_type="ortho")
        ax.set_facecolor(BG)
        ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=shade(mesh, _color(name)), edgecolors="none"))
        lo, hi = mesh.bounds
        c = (lo + hi) / 2
        s = mesh.extents.max() * 0.55
        ax.set_xlim(c[0] - s, c[0] + s); ax.set_ylim(c[1] - s, c[1] + s); ax.set_zlim(c[2] - s, c[2] + s)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=28, azim=-55)
        ax.set_axis_off()
        ax.set_title(f"{name}\n{mesh.extents[0]:.0f} x {mesh.extents[1]:.0f} x {mesh.extents[2]:.0f}", fontsize=9, color=INK, pad=0)
    fig.suptitle(title, fontsize=16, weight="bold", color=INK)
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.9, wspace=0.02, hspace=0.12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100, facecolor=BG)
    plt.close(fig)
    return path


def render_parts(cfg: TelescopeConfig, path: Path, resolution: int = 96) -> Path:
    _, meshes = _meshes(cfg, resolution)
    return render_grid(list(meshes.items()), path, f"{cfg.name}: parts in print orientation")
