import json
from pathlib import Path

from posture_guardian import config
from posture_guardian.scoring import Thresholds


def load_sensitivity(settings_path: str = config.SETTINGS_PATH) -> str:
    try:
        with open(settings_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return config.DEFAULT_SENSITIVITY
    name = data.get("sensitivity", config.DEFAULT_SENSITIVITY)
    return name if name in config.SENSITIVITY_PRESETS else config.DEFAULT_SENSITIVITY


def save_sensitivity(name: str, settings_path: str = config.SETTINGS_PATH) -> None:
    Path(settings_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = settings_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({"sensitivity": name}, f)
    Path(tmp_path).replace(settings_path)


def thresholds_for_sensitivity(name: str) -> Thresholds:
    multiplier = config.SENSITIVITY_PRESETS.get(name, config.SENSITIVITY_PRESETS[config.DEFAULT_SENSITIVITY])
    return Thresholds(
        neck_angle_margin=config.DEFAULT_THRESHOLDS["neck_angle_margin"] * multiplier,
        shoulder_tilt_margin=config.DEFAULT_THRESHOLDS["shoulder_tilt_margin"] * multiplier,
        forward_lean_margin=config.DEFAULT_THRESHOLDS["forward_lean_margin"] * multiplier,
    )
