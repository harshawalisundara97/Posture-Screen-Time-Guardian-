from pathlib import Path

APP_DIR = Path.home() / ".posture_guardian"
DB_PATH = str(APP_DIR / "posture.db")
STATUS_PATH = str(APP_DIR / "live_status.json")
PREVIEW_JPEG_PATH = str(APP_DIR / "live_preview.jpg")
PREVIEW_REQUEST_PATH = str(APP_DIR / "preview_requested")
PREVIEW_REQUEST_TIMEOUT_SECONDS = 3.0

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

SETTINGS_PATH = str(APP_DIR / "settings.json")

# Multiplier applied to DEFAULT_THRESHOLDS margins. Higher = more tolerant
# (fewer alerts), lower = stricter (more alerts).
SENSITIVITY_PRESETS = {
    "low": 1.4,
    "medium": 1.0,
    "high": 0.65,
}
DEFAULT_SENSITIVITY = "medium"

BREAK_REMINDER_SECONDS = 45 * 60
NO_PERSON_RESET_SECONDS = 60.0

LAUNCH_AGENT_LABEL = "com.nuvirahub.postureguardian"
LAUNCH_AGENT_PLIST_PATH = str(Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist")
