import datetime
import threading
import time

import cv2
import pystray
from PIL import Image, ImageDraw

from posture_guardian import config, storage
from posture_guardian.alerts import ALERT_MESSAGES, AlertDebouncer, show_overlay
from posture_guardian.calibration import run_calibration
from posture_guardian.posture_engine import PoseEngine, landmarks_to_metrics
from posture_guardian.scoring import PostureMetrics, Thresholds, classify_state, compute_score


def _make_icon_image(color: str) -> Image.Image:
    image = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, 48, 48), fill=color)
    return image


class PostureGuardianApp:
    def __init__(self):
        self.conn = storage.init_db(config.DB_PATH)
        self.thresholds = Thresholds(**config.DEFAULT_THRESHOLDS)
        self.debouncer = AlertDebouncer(
            consecutive_required=config.ALERT_CONSECUTIVE_FRAMES,
            cooldown_seconds=config.ALERT_COOLDOWN_SECONDS,
        )
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._icon = pystray.Icon(
            "posture_guardian",
            _make_icon_image("grey"),
            "Posture Guardian",
            menu=pystray.Menu(
                pystray.MenuItem("Calibrate", self._on_calibrate),
                pystray.MenuItem("Show Dashboard", self._on_show_dashboard),
                pystray.MenuItem("Pause", self._on_toggle_pause, checked=lambda item: self._paused.is_set()),
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )

    def _on_calibrate(self, icon, item):
        cap = cv2.VideoCapture(0)
        engine = PoseEngine()
        run_calibration(self.conn, cap, engine, config.CALIBRATION_FRAME_COUNT, config.CALIBRATION_MAX_STDEV)
        cap.release()
        engine.close()

    def _on_show_dashboard(self, icon, item):
        from posture_guardian.dashboard import show_dashboard

        show_dashboard(self.conn)

    def _on_toggle_pause(self, icon, item):
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    def _on_quit(self, icon, item):
        self._stop.set()
        icon.stop()

    def _detection_loop(self):
        cap = cv2.VideoCapture(0)
        engine = PoseEngine()
        good_seconds = 0.0
        monitored_seconds = 0.0
        last_flush = time.monotonic()
        frame_interval = 1.0 / config.FRAME_RATE_TARGET

        while not self._stop.is_set():
            loop_start = time.monotonic()

            if self._paused.is_set():
                self._icon.icon = _make_icon_image("grey")
                time.sleep(frame_interval)
                continue

            ok, frame = cap.read()
            if not ok:
                self._icon.icon = _make_icon_image("grey")
                time.sleep(1.0)
                continue

            landmarks = engine.process_frame(frame)
            baseline_row = storage.get_calibration(self.conn)

            if landmarks is None or baseline_row is None:
                self._icon.icon = _make_icon_image("grey")
                time.sleep(frame_interval)
                continue

            metrics = landmarks_to_metrics(landmarks)
            baseline = PostureMetrics(**baseline_row)
            state = classify_state(metrics, baseline, self.thresholds)

            monitored_seconds += frame_interval
            if state == "good":
                good_seconds += frame_interval
                self._icon.icon = _make_icon_image("green")
            else:
                self._icon.icon = _make_icon_image("red")

            storage.log_event(self.conn, datetime.datetime.now().isoformat(), state)

            if self.debouncer.update(state) and state in ALERT_MESSAGES:
                threading.Thread(target=show_overlay, args=(ALERT_MESSAGES[state],), daemon=True).start()

            if time.monotonic() - last_flush >= config.FLUSH_INTERVAL_SECONDS:
                today = datetime.date.today().isoformat()
                storage.upsert_daily_stats(self.conn, today, good_seconds, monitored_seconds)
                good_seconds = 0.0
                monitored_seconds = 0.0
                last_flush = time.monotonic()

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, frame_interval - elapsed))

        cap.release()
        engine.close()

    def start(self):
        thread = threading.Thread(target=self._detection_loop, daemon=True)
        thread.start()
        self._icon.run()

    def stop(self):
        self._stop.set()
        self._icon.stop()
