"""Print plate layout: simple shelf packing of part footprints onto the printer bed."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import trimesh

MARGIN = 8.0   # distance to the bed edge
GAP = 6.0      # distance between parts
TALL = 120.0   # parts taller than this are printed alone (less wobble, a failure costs one part)


@dataclass
class Plate:
    index: int
    items: list = field(default_factory=list)   # (name, x, y, mesh in plate coordinates)
    x: float = 0.0                              # shelf cursor
    y: float = 0.0
    row: float = 0.0

    @property
    def height(self) -> float:
        return max((m.bounds[1, 2] for _, _, _, m in self.items), default=0.0)


def pack(meshes: list[tuple[str, trimesh.Trimesh]], bed_x: float, bed_y: float, max_height: float) -> list[Plate]:
    """Place every (name, mesh) on as few plates as possible. Taller parts go first so that
    plates group parts of similar height (long prints together, short ones together)."""
    ux, uy = bed_x - 2 * MARGIN, bed_y - 2 * MARGIN
    order = sorted(meshes, key=lambda nm: (-round(nm[1].extents[2] / 20), -nm[1].extents[0] * nm[1].extents[1]))
    plates: list[Plate] = []
    for name, mesh in order:
        w, dpt, h = mesh.extents
        if w > ux or dpt > uy or h > max_height:
            raise ValueError(f"{name} ({w:.0f} x {dpt:.0f} x {h:.0f} mm) does not fit the printer")
        target = None
        for plate in ([] if h > TALL else [p for p in plates if p.height <= TALL]):   # first fit
            if plate.x + w <= ux and plate.y + dpt <= uy:
                target = plate
                break
            if plate.y + plate.row + GAP + dpt <= uy:                                   # new shelf
                plate.x, plate.y, plate.row = 0.0, plate.y + plate.row + GAP, 0.0
                target = plate
                break
        if target is None:
            target = Plate(len(plates) + 1)
            plates.append(target)
        m = mesh.copy()
        m.apply_translation((MARGIN + target.x - m.bounds[0, 0], MARGIN + target.y - m.bounds[0, 1], 0))
        target.items.append((name, MARGIN + target.x, MARGIN + target.y, m))
        target.x += w + GAP
        target.row = max(target.row, dpt)
    return plates


def export_plates(plates: list[Plate], folder: Path, prefix: str = "plate") -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for p in plates:
        assembly = trimesh.util.concatenate([m for *_, m in p.items])
        fname = f"{prefix}_{p.index:02d}.stl"
        assembly.export(folder / fname)
        out.append({"file": fname, "parts": [n for n, *_ in p.items], "height_mm": round(p.height, 1),
                    "footprint_mm": [round(v, 1) for v in assembly.extents[:2]]})
    return out
