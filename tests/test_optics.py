import math

import pytest

from telescope_generator import optics


def test_basic_formulas_against_hand_values():
    # 70/400 with a 10 mm eyepiece of 50 deg apparent field
    assert optics.magnification(400, 10) == 40
    assert optics.f_ratio(400, 70) == pytest.approx(5.714, abs=1e-3)
    assert optics.exit_pupil(70, 40) == pytest.approx(1.75)
    assert optics.true_fov_deg(50, 40) == pytest.approx(1.25)
    assert optics.dawes_arcsec(70) == pytest.approx(1.657, abs=1e-3)          # 116 / 70
    # 1.22 * 550e-6 / 70 rad = 9.586e-6 rad = 1.977 arcsec
    assert optics.rayleigh_arcsec(70) == pytest.approx(1.977, abs=1e-3)
    assert optics.max_useful_magnification(70) == 140
    assert optics.min_useful_magnification(70) == 10
    assert optics.limiting_magnitude(70) == pytest.approx(7.5 + 5 * math.log10(7))   # 11.73
    assert optics.limiting_magnitude(100) == pytest.approx(12.5)
    assert optics.light_grasp(70) == pytest.approx(100)


def test_summary_flags_excessive_magnification():
    s = optics.summary(70, 400, [(10, 50), (2, 50)])
    assert s["eyepieces"][0]["magnification"] == 40 and not s["eyepieces"][0]["over_max_useful"]
    assert s["eyepieces"][1]["magnification"] == 200 and s["eyepieces"][1]["over_max_useful"]
    assert s["f_ratio"] == 5.71
