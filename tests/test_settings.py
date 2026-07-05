from posture_guardian import config, settings


def test_load_sensitivity_defaults_when_missing(tmp_path):
    path = str(tmp_path / "settings.json")
    assert settings.load_sensitivity(path) == config.DEFAULT_SENSITIVITY


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "settings.json")
    settings.save_sensitivity("high", path)
    assert settings.load_sensitivity(path) == "high"


def test_load_sensitivity_rejects_unknown_value(tmp_path):
    path = str(tmp_path / "settings.json")
    settings.save_sensitivity("extreme", path)
    assert settings.load_sensitivity(path) == config.DEFAULT_SENSITIVITY


def test_thresholds_for_sensitivity_scales_margins():
    low = settings.thresholds_for_sensitivity("low")
    medium = settings.thresholds_for_sensitivity("medium")
    high = settings.thresholds_for_sensitivity("high")
    assert low.neck_angle_margin > medium.neck_angle_margin > high.neck_angle_margin


def test_thresholds_for_sensitivity_unknown_falls_back_to_medium():
    medium = settings.thresholds_for_sensitivity("medium")
    unknown = settings.thresholds_for_sensitivity("bogus")
    assert unknown == medium
