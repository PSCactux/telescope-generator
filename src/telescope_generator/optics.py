"""Textbook optics for a small refractor. Aperture D and focal lengths in mm.

These are the usual rules of thumb, not a ray trace:
- magnification M = F / f_eyepiece, exit pupil = D / M
- true field of view ~= apparent field / M
- Dawes limit = 116 / D arcsec; Rayleigh limit = 1.22 * lambda / D (lambda = 550 nm) = 138.4 / D arcsec
- maximum useful magnification ~= 2 x D (mm); minimum ~= D / 7 (7 mm dark-adapted pupil)
- visual limiting magnitude ~= 7.5 + 5 * log10(D in cm)
"""
from __future__ import annotations

import math

ARCSEC_PER_RAD = 180 / math.pi * 3600
WAVELENGTH_MM = 550e-6


def magnification(focal_length: float, eyepiece_focal: float) -> float:
    return focal_length / eyepiece_focal


def f_ratio(focal_length: float, aperture: float) -> float:
    return focal_length / aperture


def exit_pupil(aperture: float, mag: float) -> float:
    return aperture / mag


def true_fov_deg(apparent_fov_deg: float, mag: float) -> float:
    return apparent_fov_deg / mag


def dawes_arcsec(aperture: float) -> float:
    return 116.0 / aperture


def rayleigh_arcsec(aperture: float, wavelength_mm: float = WAVELENGTH_MM) -> float:
    return 1.22 * wavelength_mm / aperture * ARCSEC_PER_RAD


def max_useful_magnification(aperture: float) -> float:
    return 2.0 * aperture


def min_useful_magnification(aperture: float, pupil: float = 7.0) -> float:
    return aperture / pupil


def limiting_magnitude(aperture: float) -> float:
    return 7.5 + 5 * math.log10(aperture / 10)


def light_grasp(aperture: float, pupil: float = 7.0) -> float:
    """How many times more light than a 7 mm eye pupil."""
    return (aperture / pupil) ** 2


def summary(aperture: float, focal_length: float, eyepieces: list[tuple[float, float]]) -> dict:
    """eyepieces: [(focal_length, apparent_fov_deg), ...]"""
    rows = []
    for fe, afov in eyepieces:
        mag = magnification(focal_length, fe)
        rows.append({"eyepiece_mm": fe, "apparent_fov_deg": afov, "magnification": round(mag, 1),
                     "exit_pupil_mm": round(exit_pupil(aperture, mag), 2),
                     "true_fov_deg": round(true_fov_deg(afov, mag), 2),
                     "over_max_useful": mag > max_useful_magnification(aperture)})
    return {"aperture_mm": round(aperture, 2), "focal_length_mm": focal_length,
            "f_ratio": round(f_ratio(focal_length, aperture), 2),
            "dawes_arcsec": round(dawes_arcsec(aperture), 2), "rayleigh_arcsec": round(rayleigh_arcsec(aperture), 2),
            "max_useful_magnification": round(max_useful_magnification(aperture)),
            "min_useful_magnification": round(min_useful_magnification(aperture), 1),
            "limiting_magnitude": round(limiting_magnitude(aperture), 1),
            "light_grasp_vs_eye": round(light_grasp(aperture)),
            "eyepieces": rows}
