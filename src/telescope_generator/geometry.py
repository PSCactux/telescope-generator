"""CSG primitives on top of manifold3d: cylinders, helical threads, label tabs and mesh export.

All units are millimetres. Parts are built in their print orientation (flat face on z = 0).
The thread profile is a single-start trapezoid of our own (not ISO): 10 % root, 35 % flank,
10 % crest, 35 % flank, 10 % root. Clearance is always applied radially on the female side.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import manifold3d as m
import numpy as np
import trimesh

EPS = 0.02
SEGMENTS = 256  # circle resolution; 256 keeps the chord error under 0.004 mm at r = 45 mm


def set_resolution(segments: int) -> None:
    """Change the circle resolution (lower values make fast previews and tests)."""
    global SEGMENTS
    SEGMENTS = int(segments)


@dataclass(frozen=True)
class Thread:
    root: float   # root radius of the male thread
    depth: float  # radial height of the profile
    pitch: float

    @property
    def major_diameter(self) -> float:
        return 2 * (self.root + self.depth)


def cyl(r: float, h: float, z: float = 0.0, rtop: float | None = None) -> m.Manifold:
    """Cylinder or cone frustum of height h starting at z."""
    return m.Manifold.cylinder(h, r, r if rtop is None else rtop, SEGMENTS).translate((0, 0, z))


def box(x0, x1, y0, y1, z0, z1) -> m.Manifold:
    return m.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def _profile(zs: np.ndarray, theta: np.ndarray, pitch: float) -> np.ndarray:
    phase = (zs[:, None] / pitch - theta[None, :] / (2 * np.pi)) % 1
    return np.minimum(np.clip((phase - 0.10) / 0.35, 0, 1), np.clip((0.90 - phase) / 0.35, 0, 1))


def _grid_faces(nz: int, n: int, offset: int = 0, flip: bool = False) -> np.ndarray:
    j, i = np.meshgrid(np.arange(nz - 1), np.arange(n), indexing="ij")
    a = (j * n + i).ravel() + offset
    b = (j * n + (i + 1) % n).ravel() + offset
    if flip:
        f = np.concatenate([np.stack((a, b + n, b), 1), np.stack((a, a + n, b + n), 1)])
    else:
        f = np.concatenate([np.stack((a, b, b + n), 1), np.stack((a, b + n, a + n), 1)])
    return f


def _to_manifold(vertices: np.ndarray, faces: np.ndarray) -> m.Manifold:
    solid = m.Manifold(m.Mesh(np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.uint32)))
    if solid.status() != m.Error.NoError:
        raise RuntimeError(f"invalid helical mesh: {solid.status()}")
    return solid


def thread_solid(t: Thread, height: float, clearance: float = 0.0, fade: bool = False) -> m.Manifold:
    """Solid with an explicit helical surface and closed ends.

    As a male thread use clearance=0 (fade=True softens the lead-in at both ends). As a cutting
    tool for a female thread pass the radial clearance.
    """
    n = SEGMENTS
    nz = int(math.ceil(height / t.pitch * 40)) + 1
    zs = np.linspace(0, height, nz)
    theta = np.arange(n) * 2 * np.pi / n
    profile = _profile(zs, theta, t.pitch)
    if fade:
        profile *= np.clip(np.minimum(zs, height - zs) / (t.pitch * 0.5), 0, 1)[:, None]
    radii = t.root + clearance + t.depth * profile
    verts = np.stack((radii * np.cos(theta), radii * np.sin(theta), np.broadcast_to(zs[:, None], radii.shape)), -1).reshape(-1, 3)
    verts = np.vstack((verts, [0, 0, 0], [0, 0, height]))
    faces = [_grid_faces(nz, n)]
    i = np.arange(n)
    k = (i + 1) % n
    bottom, top = nz * n, nz * n + 1
    faces.append(np.stack((np.full(n, bottom), k, i), 1))
    faces.append(np.stack((np.full(n, top), (nz - 1) * n + i, (nz - 1) * n + k), 1))
    return _to_manifold(verts, np.concatenate(faces))


def female_ring(t: Thread, height: float, outer: float, clearance: float) -> m.Manifold:
    """Threaded ring built directly (no boolean): avoids slivers from two coincident helices."""
    n = SEGMENTS
    nz = int(math.ceil(height / t.pitch * 40)) + 1
    zs = np.linspace(0, height, nz)
    theta = np.arange(n) * 2 * np.pi / n
    radii = t.root + clearance + t.depth * _profile(zs, theta, t.pitch)
    lead = t.depth + 0.25
    chamfer = t.root + clearance + (t.depth + 0.1) * np.clip(1 - np.minimum(zs, height - zs) / lead, 0, 1)
    radii = np.maximum(radii, chamfer[:, None])
    verts = []
    for rr in (np.full_like(radii, outer), radii):
        verts.append(np.stack((rr * np.cos(theta), rr * np.sin(theta), np.broadcast_to(zs[:, None], rr.shape)), -1).reshape(-1, 3))
    off = nz * n
    i = np.arange(n)
    k = (i + 1) % n
    a, b = (nz - 1) * n + i, (nz - 1) * n + k
    faces = [_grid_faces(nz, n), _grid_faces(nz, n, off, flip=True),
             np.stack((i, i + off, k + off), 1), np.stack((i, k + off, k), 1),
             np.stack((a, b, b + off), 1), np.stack((a, b + off, a + off), 1)]
    return _to_manifold(np.vstack(verts), np.concatenate(faces))


def label_tab(part: m.Manifold, radius: float, label: str, h: float = 2.4) -> m.Manifold:
    """Add a tab with embossed text outside a round part, so the tested diameter is untouched."""
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.expanduser("~"), ".cache", "telescope-generator-mpl"))
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    path = TextPath((0, 0), label, size=3.4, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    bb = path.get_extents()
    width = max(30, bb.width + 5)
    y = -radius - 7
    tab = m.Manifold.cube((width, 8.5, h)).translate((-width / 2, y, 0))
    glyph = m.CrossSection(path.to_polygons(), m.FillRule.EvenOdd).extrude(0.65)
    glyph = glyph.translate((-bb.x0 - bb.width / 2, y + 2 - bb.y0, h - 0.05))
    return part + tab + glyph


class MeshError(ValueError):
    pass


def to_mesh(name: str, solid: m.Manifold) -> trimesh.Trimesh:
    """Convert to trimesh and enforce: watertight, consistent winding, positive volume,
    a single connected body and the print face on z = 0."""
    solid = solid.simplify(0.001)  # drop microscopic edges from intersections before float32 STL
    if solid.status() != m.Error.NoError:
        raise MeshError(f"{name}: manifold error {solid.status()}")
    raw = solid.to_mesh()
    mesh = trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=True)
    problems = []
    if not mesh.is_watertight:
        problems.append("not watertight")
    if not mesh.is_winding_consistent:
        problems.append("inconsistent winding")
    if mesh.volume <= 0:
        problems.append("non-positive volume")
    if len(mesh.split(only_watertight=False)) != 1:
        problems.append("more than one body")
    if abs(mesh.bounds[0, 2]) > 0.001:
        problems.append(f"print face not on z=0 (zmin={mesh.bounds[0, 2]:.3f})")
    if problems:
        raise MeshError(f"{name}: " + ", ".join(problems))
    return mesh


def thread_fit_check(male: m.Manifold, female_at, positions, step: int = 10) -> list[dict]:
    """For each axial position search a rotation with no collision, and check that some other
    rotation does collide (proves the flanks really engage). female_at(pos, angle) -> Manifold."""
    out = []
    for pos in positions:
        vols = [(male ^ female_at(pos, ang)).volume() for ang in range(0, 360, step)]
        out.append({"position": pos, "min_overlap_mm3": min(vols), "wrong_phase_overlap_mm3": max(vols),
                    "ok": min(vols) < 0.001 and max(vols) > 0.5})
    return out
