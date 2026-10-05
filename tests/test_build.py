import json

import numpy as np
import pytest
import trimesh
from conftest import EXAMPLE_70, EXAMPLE_80

from telescope_generator import geometry as g
from telescope_generator.build import build, build_gauge_set, design
from telescope_generator.cli import main
from telescope_generator.config import config_from_dict, load_config
from telescope_generator.refractor import DesignError, dimensions, lens_cell


def min_bore(mesh: trimesh.Trimesh, z: float) -> float:
    """Smallest distance from the axis to the mesh wall in the section at height z, as a diameter."""
    seg = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])[:, :, :2]
    v = seg[:, 1] - seg[:, 0]
    t = np.clip(np.sum(-seg[:, 0] * v, axis=1) / np.maximum(np.sum(v * v, axis=1), 1e-12), 0, 1)
    return float(2 * np.linalg.norm(seg[:, 0] + t[:, None] * v, axis=1).min())


@pytest.fixture(scope="module")
def built70(tmp_path_factory):
    out = tmp_path_factory.mktemp("b70")
    return out, build(load_config(EXAMPLE_70), out, log=lambda *_: None)


def test_70_400_builds_every_part_watertight(built70):
    out, summary = built70
    names = {p["name"] for p in summary["parts"]}
    expected = {"lens_cell", "lens_retainer", "tube_1", "tube_2", "spacer_16", "spacer_20", "spacer_30", "focuser_cap",
                "eyepiece_holder", "eyepiece_screw", "mount_cradle", "mount_clamp", "mount_screw", "dew_shield", "dust_cap"}
    assert expected <= names
    for p in summary["parts"]:
        mesh = trimesh.load_mesh(out / "parts" / f"{p['name']}.stl")      # STL round trip
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0, p["name"]
    assert all(c["ok"] for c in summary["checks"])
    assert (out / "summary.md").exists() and summary["plates"]
    assert json.loads((out / "summary.json").read_text())["name"] == "Refractor 70/400"


def test_70_400_reproduces_printed_v1(built70):
    """Numbers of the original 70/400 v1 that was printed and works."""
    _, s = built70
    assert s["tube_segments_mm"] == [200, 136]
    size = {p["name"]: p["size_mm"] for p in s["parts"]}
    assert size["lens_cell"] == [88, 88, 52]
    assert size["focuser_cap"][2] == 35          # 23 + 12 mm male
    assert size["eyepiece_holder"][2] == 45      # 15 flange + 30 thread (18 mm travel)
    assert s["dimensions"]["T"]["major_diameter"] == 82
    assert s["dimensions"]["F"]["major_diameter"] == 44
    assert s["focus"]["covered_with_nominal_spacer"]


def test_key_dimensions_match_the_config(built70):
    out, s = built70
    cfg = load_config(EXAMPLE_70)
    cell = trimesh.load_mesh(out / "parts" / "lens_cell.stl")
    z_pocket = s["dimensions"]["cell"]["z_pocket"]
    assert min_bore(cell, z_pocket + 8) == pytest.approx(cfg.cell_bore, abs=0.02)
    holder = trimesh.load_mesh(out / "parts" / "eyepiece_holder.stl")
    assert min_bore(holder, 8) == pytest.approx(cfg.eyepiece_bore, abs=0.02)
    tube = trimesh.load_mesh(out / "parts" / "tube_1.stl")
    assert tube.extents[0] == pytest.approx(2 * s["dimensions"]["tube_r"], abs=0.01)
    assert min_bore(tube, 100) == pytest.approx(2 * s["dimensions"]["tube_bore_r"], abs=0.02)
    # wall thickness is what the config asked for
    assert (tube.extents[0] - min_bore(tube, 100)) / 2 == pytest.approx(cfg.tube.wall_thickness, abs=0.02)


def test_80_600_unverified_example_designs(tmp_path):
    cfg = load_config(EXAMPLE_80)
    d, checks = design(cfg)
    assert all(c["ok"] for c in checks)
    assert len(d.segments) == 3 and max(d.segments) <= cfg.tube.max_segment_length


def test_lens_too_small_for_the_focuser_is_refused(data70):
    data70["objective"].update(clear_aperture=40, focal_length=300, gauge_fit_diameter=42)
    with pytest.raises(DesignError, match="too narrow"):
        dimensions(config_from_dict(data70))


def test_thin_wall_fails_a_sanity_check(data70):
    data70["tube"]["wall_thickness"] = 1.6
    with pytest.raises(DesignError, match="cell wall"):
        design(config_from_dict(data70))


def test_cell_thread_engages_a_male_probe():
    """Collision test: a free rotation exists and a wrong one collides (flanks really engage)."""
    g.set_resolution(96)
    try:
        d = dimensions(load_config(EXAMPLE_70))
        cell = lens_cell(d)
        probe = g.thread_solid(d.T, 12, fade=True)
        res = g.thread_fit_check(probe, lambda p, a: cell.rotate((0, 0, a)).translate((0, 0, p)), (0,), step=10)
    finally:
        g.set_resolution(256)
    assert res[0]["ok"], res


def test_gauges_are_watertight_and_lens_rings_have_the_right_bore(tmp_path):
    s = build_gauge_set(load_config(EXAMPLE_70), tmp_path, log=lambda *_: None)
    names = [x["name"] for x in s["gauges"]]
    assert "L_72.25" in names and "O_31.90" in names and "T_female_c25" in names and "P_c25" in names
    ring = trimesh.load_mesh(tmp_path / "parts" / "L_72.25.stl")
    assert min_bore(ring, 1.0) == pytest.approx(72.25, abs=0.02)


def test_cli_exit_codes(tmp_path, data70, capsys):
    assert main(["validate", str(EXAMPLE_70)]) == 0
    data70["objective"]["gauge_fit_diameter"] = 60
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data70))
    assert main(["build", str(bad), "--out", str(tmp_path / "o")]) == 2
    assert "smaller than the clear aperture" in capsys.readouterr().err
