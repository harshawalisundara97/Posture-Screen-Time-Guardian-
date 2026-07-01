from pathlib import Path

APP_DIR = Path.home() / ".posture_guardian"
DB_PATH = str(APP_DIR / "posture.db")

DEFAULT_THRESHOLDS = {
    "neck_angle_margin": 15.0,
    "shoulder_tilt_margin": 10.0,
    "forward_lean_margin": 0.08,
}

CALIBRATION_FRAME_COUNT = 60
CALIBRATION_MAX_STDEV = 5.0

ALERT_CONSECUTIVE_FRAMES = 45
ALERT_COOLDOWN_SECONDS = 60.0

FLUSH_INTERVAL_SECONDS = 10.0
FRAME_RATE_TARGET = 15
