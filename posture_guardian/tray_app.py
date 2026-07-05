import datetime
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import pystray
from PIL import Image, ImageDraw

from posture_guardian import config, launch_agent, settings, storage
from posture_guardian.alerts import ALERT_MESSAGES, AlertDebouncer
from posture_guardian.calibration import run_calibration
from posture_guardian.notifications import build_summary_message, send_native_notification
from posture_guardian.posture_engine import PoseEngine, landmarks_to_metrics
from posture_guardian.scoring import PostureMetrics, classify_state, compute_score

_ICON_CACHE: dict = {}


def _make_icon_image(color: str) -> Image.Image:
    if color not in _ICON_CACHE:
        image = Image.new("RGB", (64, 64), "black")
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill=color)
        _ICON_CACHE[color] = image
    return _ICON_CACHE[color]


def _spawn_overlay(message: str) -> None:
    subprocess.Popen([sys.executable, "-m", "posture_guardian.overlay_alert", message])


def _write_status(state: str, metrics=None, baseline=None) -> None:
    payload = {"state": state, "updated_at": time.time()}
    if metrics is not None:
        payload["metrics"] = {
            "neck_angle": metrics.neck_angle,
            "shoulder_tilt": metrics.shoulder_tilt,
            "forward_lean": metrics.forward_lean,
        }
    if baseline is not None:
        payload["baseline"] = {
            "neck_angle": baseline.neck_angle,
            "shoulder_tilt": baseline.shoulder_tilt,
            "forward_lean": baseline.forward_lean,
        }
    tmp_path = config.STATUS_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(payload, f)
    Path(tmp_path).replace(config.STATUS_PATH)


def _preview_requested() -> bool:
    try:
        age = time.time() - Path(config.PREVIEW_REQUEST_PATH).stat().st_mtime
    except FileNotFoundError:
        return False
    return age <= config.PREVIEW_REQUEST_TIMEOUT_SECONDS


def _write_preview(frame, border_color) -> None:
    bordered = cv2.copyMakeBorder(frame, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=border_color)
    ok, buf = cv2.imencode(".jpg", bordered, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return
    tmp_path = config.PREVIEW_JPEG_PATH + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(buf.tobytes())
    Path(tmp_path).replace(config.PREVIEW_JPEG_PATH)


_BGR_BY_STATE = {
    "good": (0, 180, 0),
    "slouching": (0, 0, 220),
    "too_close": (0, 0, 220),
    "neck_bent": (0, 0, 220),
}


class PostureGuardianApp:
    def __init__(self):
        self.conn = storage.init_db(config.DB_PATH)
        self.sensitivity = settings.load_sensitivity()
        self.thresholds = settings.thresholds_for_sensitivity(self.sensitivity)
        self.debouncer = AlertDebouncer(
            consecutive_required=config.ALERT_CONSECUTIVE_FRAMES,
            cooldown_seconds=config.ALERT_COOLDOWN_SECONDS,
        )
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._calibrating = threading.Event()
        self._calibrate_lock = threading.Lock()
        self._sit_seconds = 0.0
        self._no_person_seconds = 0.0
        self._last_seen_date = datetime.date.today().isoformat()
        self._icon = pystray.Icon(
            "posture_guardian",
            _make_icon_image("grey"),
            "Posture Guardian",
            menu=pystray.Menu(
                pystray.MenuItem("Calibrate", self._on_calibrate),
                pystray.MenuItem("Show Dashboard", self._on_show_dashboard),
                pystray.MenuItem("Pause", self._on_toggle_pause, checked=lambda item: self._paused.is_set()),
                pystray.MenuItem(
                    "Sensitivity",
                    pystray.Menu(
                        pystray.MenuItem(
                            "Low",
                            self._make_sensitivity_setter("low"),
                            checked=lambda item: self.sensitivity == "low",
                            radio=True,
                        ),
                        pystray.MenuItem(
                            "Medium",
                            self._make_sensitivity_setter("medium"),
                            checked=lambda item: self.sensitivity == "medium",
                            radio=True,
                        ),
                        pystray.MenuItem(
                            "High",
                            self._make_sensitivity_setter("high"),
                            checked=lambda item: self.sensitivity == "high",
                            radio=True,
                        ),
                    ),
                ),
                pystray.MenuItem(
                    "Launch at Login",
                    self._on_toggle_launch_at_login,
                    checked=lambda item: launch_agent.is_enabled(config.LAUNCH_AGENT_PLIST_PATH),
                ),
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )

    def _make_sensitivity_setter(self, name):
        def _set(icon, item):
            self.sensitivity = name
            self.thresholds = settings.thresholds_for_sensitivity(name)
            settings.save_sensitivity(name)

        return _set

    def _on_toggle_launch_at_login(self, icon, item):
        if launch_agent.is_enabled(config.LAUNCH_AGENT_PLIST_PATH):
            launch_agent.disable(config.LAUNCH_AGENT_PLIST_PATH, config.LAUNCH_AGENT_LABEL)
        else:
            launch_agent.enable(
                config.LAUNCH_AGENT_PLIST_PATH,
                config.LAUNCH_AGENT_LABEL,
                sys.executable,
                "posture_guardian.main",
            )

    def _on_calibrate(self, icon, item):
        if not self._calibrate_lock.acquire(blocking=False):
            return  # already calibrating; ignore double-click
        try:
            self._calibrating.set()
            time.sleep(0.15)  # give detection loop time to release the camera
            _spawn_overlay("Calibrating — sit up straight and hold still")
            cap = cv2.VideoCapture(0)
            engine = PoseEngine()
            try:
                ok = run_calibration(self.conn, cap, engine, config.CALIBRATION_FRAME_COUNT, config.CALIBRATION_MAX_STDEV)
                _spawn_overlay("Calibration saved" if ok else "Calibration failed — hold still and try again")
            finally:
                cap.release()
                engine.close()
        finally:
            self._calibrating.clear()
            self._calibrate_lock.release()

    def _on_show_dashboard(self, icon, item):
        subprocess.Popen([sys.executable, "-m", "posture_guardian.dashboard_entry"])

    def _on_toggle_pause(self, icon, item):
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    def _on_quit(self, icon, item):
        self._send_daily_summary(datetime.date.today().isoformat())
        self._stop.set()
        icon.stop()

    def _send_daily_summary(self, date_str: str) -> None:
        stats = storage.get_daily_stats(self.conn, date_str)
        if stats["monitored_seconds"] <= 0:
            return
        score = compute_score(stats["good_seconds"], stats["monitored_seconds"])

        previous_date = (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=1)).isoformat()
        previous_stats = storage.get_daily_stats(self.conn, previous_date)
        previous_score = (
            compute_score(previous_stats["good_seconds"], previous_stats["monitored_seconds"])
            if previous_stats["monitored_seconds"] > 0
            else None
        )

        message = build_summary_message(date_str, score, previous_score)
        send_native_notification("Posture Guardian — Daily Summary", message)

    def _detection_loop(self):
        cap = None
        engine = PoseEngine()
        good_seconds = 0.0
        monitored_seconds = 0.0
        last_flush = time.monotonic()
        frame_interval = 1.0 / config.FRAME_RATE_TARGET

        while not self._stop.is_set():
            loop_start = time.monotonic()

            today = datetime.date.today().isoformat()
            if today != self._last_seen_date:
                self._send_daily_summary(self._last_seen_date)
                self._last_seen_date = today

            if self._paused.is_set() or self._calibrating.is_set():
                # Release camera so calibration (or pause) can use it
                if cap is not None:
                    cap.release()
                    cap = None
                self._icon.icon = _make_icon_image("grey")
                state_name = "paused" if self._paused.is_set() else "calibrating"
                self._icon.title = f"Posture Guardian — {state_name}"
                _write_status(state_name)
                self._sit_seconds = 0.0
                time.sleep(frame_interval)
                continue

            # Ensure camera is open
            if cap is None:
                cap = cv2.VideoCapture(0)

            ok, frame = cap.read()
            if not ok:
                self._icon.icon = _make_icon_image("grey")
                _write_status("no_camera")
                time.sleep(1.0)
                continue

            landmarks = engine.process_frame(frame)
            baseline_row = storage.get_calibration(self.conn)

            if baseline_row is None:
                self._icon.icon = _make_icon_image("grey")
                _write_status("not_calibrated")
                time.sleep(frame_interval)
                continue

            if landmarks is None:
                self._icon.icon = _make_icon_image("grey")
                _write_status("no_person")
                self._no_person_seconds += frame_interval
                if self._no_person_seconds >= config.NO_PERSON_RESET_SECONDS:
                    self._sit_seconds = 0.0
                time.sleep(frame_interval)
                continue

            self._no_person_seconds = 0.0
            metrics = landmarks_to_metrics(landmarks)
            baseline = PostureMetrics(**baseline_row)
            state = classify_state(metrics, baseline, self.thresholds)

            self._sit_seconds += frame_interval
            if self._sit_seconds >= config.BREAK_REMINDER_SECONDS:
                _spawn_overlay("Time for a break — you've been sitting a while")
                self._sit_seconds = 0.0

            monitored_seconds += frame_interval
            if state == "good":
                good_seconds += frame_interval
                self._icon.icon = _make_icon_image("green")
            else:
                self._icon.icon = _make_icon_image("red")
            self._icon.title = f"Posture Guardian — {state.replace('_', ' ')}"

            storage.log_event(self.conn, datetime.datetime.now().isoformat(), state)
            _write_status(state, metrics=metrics, baseline=baseline)

            if _preview_requested():
                _write_preview(frame, _BGR_BY_STATE.get(state, (120, 120, 120)))

            if self.debouncer.update(state) and state in ALERT_MESSAGES:
                _spawn_overlay(ALERT_MESSAGES[state])

            if time.monotonic() - last_flush >= config.FLUSH_INTERVAL_SECONDS:
                today = datetime.date.today().isoformat()
                storage.upsert_daily_stats(self.conn, today, good_seconds, monitored_seconds)
                good_seconds = 0.0
                monitored_seconds = 0.0
                last_flush = time.monotonic()

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, frame_interval - elapsed))

        if monitored_seconds > 0:
            today = datetime.date.today().isoformat()
            storage.upsert_daily_stats(self.conn, today, good_seconds, monitored_seconds)
        if cap is not None:
            cap.release()
        engine.close()

    def start(self):
        # macOS can only prompt for camera authorization from the main thread;
        # opening the capture here first (before the daemon thread exists)
        # triggers that prompt and lets AVFoundation finish authorizing.
        warmup_cap = cv2.VideoCapture(0)
        warmup_cap.read()
        warmup_cap.release()

        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        self._icon.run()
        # icon.run() returned (Quit clicked): let the detection loop finish its
        # current iteration, then close the DB connection cleanly.
        self._stop.set()
        self._thread.join(timeout=3.0)
        self.conn.close()

    def stop(self):
        self._stop.set()
        self._icon.stop()
