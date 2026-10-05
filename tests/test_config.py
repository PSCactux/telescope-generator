import copy

import pytest
from conftest import EXAMPLE_70, EXAMPLE_80

from telescope_generator.config import ConfigError, config_from_dict, load_config


def test_examples_load():
    cfg = load_config(EXAMPLE_70)
    assert cfg.verified and cfg.cell_bore == 72.25 and cfg.eyepiece_bore == 31.9
    cfg80 = load_config(EXAMPLE_80)
    assert not cfg80.verified
    assert cfg80.cell_bore == pytest.approx(82.0 + 2 * 0.15)          # measured + clearance
    assert cfg80.eyepiece_bore == pytest.approx(31.75 + 2 * 0.075)


def _errors(data) -> list[str]:
    with pytest.raises(ConfigError) as exc:
        config_from_dict(data)
    return exc.value.problems


def test_missing_required(data70):
    del data70["objective"]
    assert any("objective: required" in p for p in _errors(data70))


def test_unknown_key_is_reported(data70):
    data70["objective"]["diameter"] = 70
    assert any("objective.diameter: unknown key" in p for p in _errors(data70))


def test_out_of_range_and_type_errors_are_all_listed(data70):
    data70["objective"]["focal_length"] = "four hundred"
    data70["tube"]["wall_thickness"] = 0.5
    probs = _errors(data70)
    assert len(probs) == 2
    assert any("focal_length: must be a number" in p for p in probs)
    assert any("wall_thickness" in p for p in probs)


def test_lens_smaller_than_aperture_is_impossible(data70):
    data70["objective"]["gauge_fit_diameter"] = 65
    assert any("smaller than the clear aperture" in p for p in _errors(data70))


def test_eyepiece_bore_must_exceed_barrel(data70):
    data70["eyepiece_holder"]["gauge_fit_bore"] = 31.7
    assert any("must be larger than the barrel" in p for p in _errors(data70))


def test_needs_gauge_or_measurement(data70):
    del data70["objective"]["gauge_fit_diameter"]
    assert any("gauge_fit_diameter" in p for p in _errors(data70))


def test_segment_longer_than_printer(data70):
    data70["tube"]["max_segment_length"] = 300
    assert any("exceeds printer.max_height" in p for p in _errors(data70))


def test_bad_tripod_mode(data70):
    data70["tripod"]["mode"] = "glue"
    assert any("tripod.mode" in p for p in _errors(data70))


def test_field_stop_outside_barrel(data70):
    data70["eyepiece_holder"]["field_stop_depth"] = 25
    assert any("field_stop_depth" in p for p in _errors(data70))


def test_unrealistic_f_ratio(data70):
    d = copy.deepcopy(data70)
    d["objective"]["focal_length"] = 150
    assert any("faster than f/3" in p for p in _errors(d))
