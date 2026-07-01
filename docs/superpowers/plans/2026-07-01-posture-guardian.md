# Posture & Screen-Time Guardian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS Python tray app that watches posture via webcam (MediaPipe Pose), alerts with an on-screen overlay when the user slouches/leans too close/bends their neck, and tracks a daily posture score in SQLite.

**Architecture:** A background thread runs webcam capture → MediaPipe Pose → pure metric/scoring functions → debounced alert overlay. A `pystray` tray icon on the main thread owns the thread and exposes Calibrate / Show Dashboard / Pause / Quit. SQLite stores the user's calibrated baseline and daily aggregated stats; a `tkinter` dashboard window reads from it.

**Tech Stack:** Python 3.11+, `opencv-python`, `mediapipe`, `pystray`, `Pillow`, `tkinter` (stdlib), `sqlite3` (stdlib), `pytest`.

## Global Constraints

- Target platform: macOS only for this MVP (per spec Non-goals).
- No cloud backend, accounts, sync, or screen-time tracking in this build (per spec Non-goals).
- No persistent camera preview / skeleton overlay UI — detection is headless (per spec Goals).
- Pure logic (scoring, calibration math, debounce, landmark→metric geometry) must be unit-testable without a camera or display; camera/UI-dependent code is manually verified and explicitly called out as such (per spec Testing section).
- SQLite schema: `calibration` (one baseline row), `daily_stats` (date, good_seconds, monitored_seconds), `events` (timestamp, state) — per spec Components.

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `posture_guardian/__init__.py`
- Create: `posture_guardian/config.py`
- Create: `.gitignore`
- Create: `README.md`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `posture_guardian.config` module with constants: `APP_DIR: Path`, `DB_PATH: str`, `DEFAULT_THRESHOLDS: dict`, `CALIBRATION_FRAME_COUNT: int`, `CALIBRATION_MAX_STDEV: float`, `ALERT_CONSECUTIVE_FRAMES: int`, `ALERT_COOLDOWN_SECONDS: float`, `FLUSH_INTERVAL_SECONDS: float`, `FRAME_RATE_TARGET: int`.

- [ ] **Step 1: Create the package layout**

```bash
mkdir -p /Users/ranjana/Harsha/Projects/posture/posture_guardian
mkdir -p /Users/ranjana/Harsha/Projects/posture/tests
touch /Users/ranjana/Harsha/Projects/posture/posture_guardian/__init__.py
touch /Users/ranjana/Harsha/Projects/posture/tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
opencv-python>=4.9
mediapipe>=0.10
pystray>=0.19
Pillow>=10.0
pytest>=8.0
```

- [ ] **Step 3: Write `posture_guardian/config.py`**

```python
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
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
*.db
.DS_Store
```

- [ ] **Step 5: Write `README.md`**

```markdown
# Posture & Screen-Time Guardian

Webcam-based posture guardian for desk workers. Runs as a macOS tray app,
alerts on slouching / leaning too close / neck bend, tracks a daily posture score.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

## Run

    python -m posture_guardian.main

## Test

    pytest
```

- [ ] **Step 6: Set up a virtualenv and install dependencies**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error. If `mediapipe` fails to install on the current Python version, note the Python version (`python3 --version`) — mediapipe requires 3.9–3.12 as of this writing; switch to a compatible interpreter if needed.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt posture_guardian .gitignore README.md tests
git commit -m "Scaffold project structure and config"
```

---

## Task 2: `storage.py` — SQLite persistence

**Files:**
- Create: `posture_guardian/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: nothing (uses stdlib `sqlite3` only).
- Produces: `init_db(db_path: str) -> sqlite3.Connection`, `save_calibration(conn, neck_angle: float, shoulder_tilt: float, forward_lean: float) -> None`, `get_calibration(conn) -> dict | None`, `upsert_daily_stats(conn, date: str, good_seconds: float, monitored_seconds: float) -> None`, `get_daily_stats(conn, date: str) -> dict`, `get_recent_stats(conn, days: int) -> list[dict]`, `log_event(conn, timestamp: str, state: str) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage.py
import pytest
from posture_guardian import storage


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    return storage.init_db(db_path)


def test_calibration_round_trip(conn):
    assert storage.get_calibration(conn) is None
    storage.save_calibration(conn, neck_angle=12.5, shoulder_tilt=1.2, forward_lean=0.3)
    baseline = storage.get_calibration(conn)
    assert baseline == {"neck_angle": 12.5, "shoulder_tilt": 1.2, "forward_lean": 0.3}


def test_save_calibration_overwrites_previous(conn):
    storage.save_calibration(conn, neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2)
    storage.save_calibration(conn, neck_angle=20.0, shoulder_tilt=2.0, forward_lean=0.4)
    baseline = storage.get_calibration(conn)
    assert baseline == {"neck_angle": 20.0, "shoulder_tilt": 2.0, "forward_lean": 0.4}


def test_daily_stats_accumulate(conn):
    storage.upsert_daily_stats(conn, "2026-07-01", good_seconds=10.0, monitored_seconds=15.0)
    storage.upsert_daily_stats(conn, "2026-07-01", good_seconds=5.0, monitored_seconds=5.0)
    stats = storage.get_daily_stats(conn, "2026-07-01")
    assert stats == {"good_seconds": 15.0, "monitored_seconds": 20.0}


def test_daily_stats_missing_date_returns_zeros(conn):
    stats = storage.get_daily_stats(conn, "2026-01-01")
    assert stats == {"good_seconds": 0.0, "monitored_seconds": 0.0}


def test_recent_stats_ordered_desc_and_limited(conn):
    storage.upsert_daily_stats(conn, "2026-06-28", good_seconds=1.0, monitored_seconds=2.0)
    storage.upsert_daily_stats(conn, "2026-06-29", good_seconds=1.0, monitored_seconds=2.0)
    storage.upsert_daily_stats(conn, "2026-06-30", good_seconds=1.0, monitored_seconds=2.0)
    recent = storage.get_recent_stats(conn, days=2)
    assert [r["date"] for r in recent] == ["2026-06-30", "2026-06-29"]


def test_log_event_inserts_row(conn):
    storage.log_event(conn, timestamp="2026-07-01T10:00:00", state="slouching")
    row = conn.execute("SELECT timestamp, state FROM events").fetchone()
    assert row == ("2026-07-01T10:00:00", "slouching")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/ranjana/Harsha/Projects/posture
pytest tests/test_storage.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `AttributeError` — `posture_guardian.storage` doesn't exist yet.

- [ ] **Step 3: Write `posture_guardian/storage.py`**

```python
import sqlite3
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS calibration (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    neck_angle REAL NOT NULL,
    shoulder_tilt REAL NOT NULL,
    forward_lean REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    good_seconds REAL NOT NULL DEFAULT 0,
    monitored_seconds REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    state TEXT NOT NULL
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_calibration(conn: sqlite3.Connection, neck_angle: float, shoulder_tilt: float, forward_lean: float) -> None:
    conn.execute(
        """
        INSERT INTO calibration (id, neck_angle, shoulder_tilt, forward_lean)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            neck_angle = excluded.neck_angle,
            shoulder_tilt = excluded.shoulder_tilt,
            forward_lean = excluded.forward_lean
        """,
        (neck_angle, shoulder_tilt, forward_lean),
    )
    conn.commit()


def get_calibration(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute(
        "SELECT neck_angle, shoulder_tilt, forward_lean FROM calibration WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    return {"neck_angle": row[0], "shoulder_tilt": row[1], "forward_lean": row[2]}


def upsert_daily_stats(conn: sqlite3.Connection, date: str, good_seconds: float, monitored_seconds: float) -> None:
    conn.execute(
        """
        INSERT INTO daily_stats (date, good_seconds, monitored_seconds)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            good_seconds = daily_stats.good_seconds + excluded.good_seconds,
            monitored_seconds = daily_stats.monitored_seconds + excluded.monitored_seconds
        """,
        (date, good_seconds, monitored_seconds),
    )
    conn.commit()


def get_daily_stats(conn: sqlite3.Connection, date: str) -> dict:
    row = conn.execute(
        "SELECT good_seconds, monitored_seconds FROM daily_stats WHERE date = ?", (date,)
    ).fetchone()
    if row is None:
        return {"good_seconds": 0.0, "monitored_seconds": 0.0}
    return {"good_seconds": row[0], "monitored_seconds": row[1]}


def get_recent_stats(conn: sqlite3.Connection, days: int) -> list[dict]:
    rows = conn.execute(
        "SELECT date, good_seconds, monitored_seconds FROM daily_stats ORDER BY date DESC LIMIT ?",
        (days,),
    ).fetchall()
    return [{"date": r[0], "good_seconds": r[1], "monitored_seconds": r[2]} for r in rows]


def log_event(conn: sqlite3.Connection, timestamp: str, state: str) -> None:
    conn.execute("INSERT INTO events (timestamp, state) VALUES (?, ?)", (timestamp, state))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_storage.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add posture_guardian/storage.py tests/test_storage.py
git commit -m "Add SQLite storage layer for calibration and daily stats"
```

---

## Task 3: `scoring.py` — posture classification and score math

**Files:**
- Create: `posture_guardian/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PostureMetrics` dataclass (`neck_angle: float`, `shoulder_tilt: float`, `forward_lean: float`), `Thresholds` dataclass (`neck_angle_margin: float = 15.0`, `shoulder_tilt_margin: float = 10.0`, `forward_lean_margin: float = 0.08`), `classify_state(metrics: PostureMetrics, baseline: PostureMetrics, thresholds: Thresholds) -> str` (returns one of `"good"`, `"too_close"`, `"neck_bent"`, `"slouching"`), `compute_score(good_seconds: float, monitored_seconds: float) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scoring.py
from posture_guardian.scoring import PostureMetrics, Thresholds, classify_state, compute_score

BASELINE = PostureMetrics(neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.20)
THRESHOLDS = Thresholds(neck_angle_margin=15.0, shoulder_tilt_margin=10.0, forward_lean_margin=0.08)


def test_classify_good_posture_matches_baseline():
    metrics = PostureMetrics(neck_angle=11.0, shoulder_tilt=1.5, forward_lean=0.21)
    assert classify_state(metrics, BASELINE, THRESHOLDS) == "good"


def test_classify_too_close_when_forward_lean_exceeds_margin():
    metrics = PostureMetrics(neck_angle=11.0, shoulder_tilt=1.5, forward_lean=0.35)
    assert classify_state(metrics, BASELINE, THRESHOLDS) == "too_close"


def test_classify_neck_bent_when_neck_angle_exceeds_margin():
    metrics = PostureMetrics(neck_angle=30.0, shoulder_tilt=1.5, forward_lean=0.21)
    assert classify_state(metrics, BASELINE, THRESHOLDS) == "neck_bent"


def test_classify_slouching_when_shoulder_tilt_exceeds_margin():
    metrics = PostureMetrics(neck_angle=11.0, shoulder_tilt=15.0, forward_lean=0.21)
    assert classify_state(metrics, BASELINE, THRESHOLDS) == "slouching"


def test_classify_priority_forward_lean_over_neck_and_shoulder():
    metrics = PostureMetrics(neck_angle=30.0, shoulder_tilt=15.0, forward_lean=0.35)
    assert classify_state(metrics, BASELINE, THRESHOLDS) == "too_close"


def test_compute_score_percentage():
    assert compute_score(good_seconds=45.0, monitored_seconds=60.0) == 75.0


def test_compute_score_zero_monitored_time_returns_zero():
    assert compute_score(good_seconds=0.0, monitored_seconds=0.0) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `posture_guardian/scoring.py`**

```python
from dataclasses import dataclass


@dataclass
class PostureMetrics:
    neck_angle: float
    shoulder_tilt: float
    forward_lean: float


@dataclass
class Thresholds:
    neck_angle_margin: float = 15.0
    shoulder_tilt_margin: float = 10.0
    forward_lean_margin: float = 0.08


def classify_state(metrics: PostureMetrics, baseline: PostureMetrics, thresholds: Thresholds) -> str:
    if metrics.forward_lean - baseline.forward_lean > thresholds.forward_lean_margin:
        return "too_close"
    if abs(metrics.neck_angle - baseline.neck_angle) > thresholds.neck_angle_margin:
        return "neck_bent"
    if abs(metrics.shoulder_tilt - baseline.shoulder_tilt) > thresholds.shoulder_tilt_margin:
        return "slouching"
    return "good"


def compute_score(good_seconds: float, monitored_seconds: float) -> float:
    if monitored_seconds <= 0:
        return 0.0
    return round((good_seconds / monitored_seconds) * 100, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scoring.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add posture_guardian/scoring.py tests/test_scoring.py
git commit -m "Add posture scoring: classification and daily score math"
```

---

## Task 4: `posture_engine.py` — landmark geometry (pure part)

**Files:**
- Create: `posture_guardian/posture_engine.py`
- Test: `tests/test_posture_engine.py`

**Interfaces:**
- Consumes: `PostureMetrics` from `posture_guardian.scoring`.
- Produces: `Landmark` dataclass (`x: float`, `y: float`), `PoseLandmarks` dataclass (`nose: Landmark`, `left_shoulder: Landmark`, `right_shoulder: Landmark`, `left_ear: Landmark`, `right_ear: Landmark`), `landmarks_to_metrics(landmarks: PoseLandmarks) -> PostureMetrics`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_posture_engine.py
from posture_guardian.posture_engine import Landmark, PoseLandmarks, landmarks_to_metrics


def upright_landmarks():
    return PoseLandmarks(
        nose=Landmark(x=0.50, y=0.20),
        left_shoulder=Landmark(x=0.40, y=0.40),
        right_shoulder=Landmark(x=0.60, y=0.40),
        left_ear=Landmark(x=0.47, y=0.22),
        right_ear=Landmark(x=0.53, y=0.22),
    )


def test_landmarks_to_metrics_returns_expected_fields():
    metrics = landmarks_to_metrics(upright_landmarks())
    assert hasattr(metrics, "neck_angle")
    assert hasattr(metrics, "shoulder_tilt")
    assert hasattr(metrics, "forward_lean")


def test_shoulder_tilt_zero_when_shoulders_level():
    metrics = landmarks_to_metrics(upright_landmarks())
    assert metrics.shoulder_tilt == 0.0


def test_shoulder_tilt_positive_when_shoulders_uneven():
    landmarks = upright_landmarks()
    landmarks.left_shoulder = Landmark(x=0.40, y=0.45)
    metrics = landmarks_to_metrics(landmarks)
    assert metrics.shoulder_tilt == pytest_approx(0.05)


def pytest_approx(value, tol=1e-6):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) < tol
    return _Approx()


def test_forward_lean_increases_as_shoulders_get_wider():
    narrow = upright_landmarks()
    metrics_narrow = landmarks_to_metrics(narrow)

    wide = upright_landmarks()
    wide.left_shoulder = Landmark(x=0.30, y=0.40)
    wide.right_shoulder = Landmark(x=0.70, y=0.40)
    metrics_wide = landmarks_to_metrics(wide)

    assert metrics_wide.forward_lean > metrics_narrow.forward_lean


def test_neck_angle_near_zero_when_ears_directly_above_shoulders():
    landmarks = PoseLandmarks(
        nose=Landmark(x=0.50, y=0.20),
        left_shoulder=Landmark(x=0.45, y=0.40),
        right_shoulder=Landmark(x=0.55, y=0.40),
        left_ear=Landmark(x=0.47, y=0.20),
        right_ear=Landmark(x=0.53, y=0.20),
    )
    metrics = landmarks_to_metrics(landmarks)
    assert metrics.neck_angle < 5.0


def test_neck_angle_large_when_head_juts_forward():
    landmarks = PoseLandmarks(
        nose=Landmark(x=0.60, y=0.20),
        left_shoulder=Landmark(x=0.45, y=0.40),
        right_shoulder=Landmark(x=0.55, y=0.40),
        left_ear=Landmark(x=0.65, y=0.22),
        right_ear=Landmark(x=0.71, y=0.22),
    )
    metrics = landmarks_to_metrics(landmarks)
    assert metrics.neck_angle > 30.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_posture_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the pure geometry part of `posture_guardian/posture_engine.py`**

```python
import math
from dataclasses import dataclass

from posture_guardian.scoring import PostureMetrics


@dataclass
class Landmark:
    x: float
    y: float


@dataclass
class PoseLandmarks:
    nose: Landmark
    left_shoulder: Landmark
    right_shoulder: Landmark
    left_ear: Landmark
    right_ear: Landmark


def _midpoint(a: Landmark, b: Landmark) -> Landmark:
    return Landmark(x=(a.x + b.x) / 2, y=(a.y + b.y) / 2)


def landmarks_to_metrics(landmarks: PoseLandmarks) -> PostureMetrics:
    shoulder_mid = _midpoint(landmarks.left_shoulder, landmarks.right_shoulder)
    ear_mid = _midpoint(landmarks.left_ear, landmarks.right_ear)

    dx = shoulder_mid.x - ear_mid.x
    dy = shoulder_mid.y - ear_mid.y
    neck_angle = math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 90.0

    shoulder_tilt = abs(landmarks.left_shoulder.y - landmarks.right_shoulder.y)

    forward_lean = math.hypot(
        landmarks.left_shoulder.x - landmarks.right_shoulder.x,
        landmarks.left_shoulder.y - landmarks.right_shoulder.y,
    )

    return PostureMetrics(neck_angle=neck_angle, shoulder_tilt=shoulder_tilt, forward_lean=forward_lean)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_posture_engine.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add posture_guardian/posture_engine.py tests/test_posture_engine.py
git commit -m "Add pure landmark-to-metrics geometry"
```

---

## Task 5: `posture_engine.py` — MediaPipe/OpenCV camera wrapper (manual verification)

**Files:**
- Modify: `posture_guardian/posture_engine.py`

**Interfaces:**
- Consumes: `Landmark`, `PoseLandmarks` from this same module (Task 4).
- Produces: `PoseEngine` class with `process_frame(frame_bgr) -> PoseLandmarks | None` and `close() -> None`.

**Why this is manual-only:** this class talks to a real webcam and the real MediaPipe model; there is no meaningful way to unit test it without faking both, and faking both would only test the fake. Per spec Testing section, this is verified manually, not by an automated suite.

- [ ] **Step 1: Append the `PoseEngine` class to `posture_guardian/posture_engine.py`**

```python
class PoseEngine:
    """Wraps MediaPipe Pose for a live webcam feed. Manual-verification only — see Task 5 of the plan."""

    def __init__(self):
        import mediapipe as mp

        self._mp_pose_module = mp.solutions.pose
        self._pose = self._mp_pose_module.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def process_frame(self, frame_bgr):
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)
        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        idx = self._mp_pose_module.PoseLandmark

        def pt(landmark_id):
            p = lm[landmark_id]
            return Landmark(x=p.x, y=p.y)

        return PoseLandmarks(
            nose=pt(idx.NOSE),
            left_shoulder=pt(idx.LEFT_SHOULDER),
            right_shoulder=pt(idx.RIGHT_SHOULDER),
            left_ear=pt(idx.LEFT_EAR),
            right_ear=pt(idx.RIGHT_EAR),
        )

    def close(self):
        self._pose.close()
```

- [ ] **Step 2: Write a manual smoke-test script**

```python
# scripts/manual_pose_check.py
import time
import cv2
from posture_guardian.posture_engine import PoseEngine
from posture_guardian.posture_engine import landmarks_to_metrics

cap = cv2.VideoCapture(0)
engine = PoseEngine()

print("Sit in view of the webcam. Printing metrics for 5 seconds...")
start = time.time()
while time.time() - start < 5:
    ok, frame = cap.read()
    if not ok:
        print("Failed to read from webcam")
        break
    landmarks = engine.process_frame(frame)
    if landmarks is None:
        print("no person detected")
        continue
    metrics = landmarks_to_metrics(landmarks)
    print(f"neck_angle={metrics.neck_angle:.1f} shoulder_tilt={metrics.shoulder_tilt:.3f} forward_lean={metrics.forward_lean:.3f}")

cap.release()
engine.close()
```

```bash
mkdir -p /Users/ranjana/Harsha/Projects/posture/scripts
```

Save the script above to `scripts/manual_pose_check.py`, then run:

```bash
cd /Users/ranjana/Harsha/Projects/posture
python scripts/manual_pose_check.py
```

Expected: macOS prompts for camera permission on first run (grant it); the script prints a line of metrics roughly 5-10 times per second while a person is in frame, and prints `no person detected` when no one is in frame. Confirm `neck_angle` visibly increases when you lean your head forward, and `forward_lean` visibly increases when you move closer to the camera.

- [ ] **Step 3: Commit**

```bash
git add posture_guardian/posture_engine.py scripts/manual_pose_check.py
git commit -m "Add MediaPipe camera wrapper (manually verified)"
```

---

## Task 6: `calibration.py` — pure calibration math

**Files:**
- Create: `posture_guardian/calibration.py`
- Test: `tests/test_calibration.py`

**Interfaces:**
- Consumes: `PostureMetrics` from `posture_guardian.scoring`.
- Produces: `average_metrics(samples: list[PostureMetrics]) -> PostureMetrics`, `is_motion_too_high(samples: list[PostureMetrics], max_stdev: float) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_calibration.py
from posture_guardian.scoring import PostureMetrics
from posture_guardian.calibration import average_metrics, is_motion_too_high


def test_average_metrics_computes_mean_of_each_field():
    samples = [
        PostureMetrics(neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2),
        PostureMetrics(neck_angle=20.0, shoulder_tilt=2.0, forward_lean=0.4),
    ]
    avg = average_metrics(samples)
    assert avg == PostureMetrics(neck_angle=15.0, shoulder_tilt=1.5, forward_lean=0.3)


def test_is_motion_too_high_false_when_samples_are_stable():
    samples = [
        PostureMetrics(neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2),
        PostureMetrics(neck_angle=10.2, shoulder_tilt=1.1, forward_lean=0.21),
        PostureMetrics(neck_angle=9.9, shoulder_tilt=0.9, forward_lean=0.19),
    ]
    assert is_motion_too_high(samples, max_stdev=5.0) is False


def test_is_motion_too_high_true_when_samples_vary_a_lot():
    samples = [
        PostureMetrics(neck_angle=5.0, shoulder_tilt=1.0, forward_lean=0.2),
        PostureMetrics(neck_angle=40.0, shoulder_tilt=1.0, forward_lean=0.2),
        PostureMetrics(neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2),
    ]
    assert is_motion_too_high(samples, max_stdev=5.0) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_calibration.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the pure part of `posture_guardian/calibration.py`**

```python
from statistics import mean, pstdev

from posture_guardian.scoring import PostureMetrics


def average_metrics(samples: list[PostureMetrics]) -> PostureMetrics:
    return PostureMetrics(
        neck_angle=mean(s.neck_angle for s in samples),
        shoulder_tilt=mean(s.shoulder_tilt for s in samples),
        forward_lean=mean(s.forward_lean for s in samples),
    )


def is_motion_too_high(samples: list[PostureMetrics], max_stdev: float) -> bool:
    neck_angles = [s.neck_angle for s in samples]
    shoulder_tilts = [s.shoulder_tilt for s in samples]
    forward_leans = [s.forward_lean for s in samples]
    return (
        pstdev(neck_angles) > max_stdev
        or pstdev(shoulder_tilts) > max_stdev
        or pstdev(forward_leans) > max_stdev
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_calibration.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add posture_guardian/calibration.py tests/test_calibration.py
git commit -m "Add pure calibration math: averaging and motion check"
```

---

## Task 7: `calibration.py` — guided capture flow (manual verification)

**Files:**
- Modify: `posture_guardian/calibration.py`

**Interfaces:**
- Consumes: `average_metrics`, `is_motion_too_high` (Task 6); `PoseEngine`, `landmarks_to_metrics` from `posture_guardian.posture_engine` (Task 5); `save_calibration` from `posture_guardian.storage` (Task 2); `CALIBRATION_FRAME_COUNT`, `CALIBRATION_MAX_STDEV` from `posture_guardian.config` (Task 1).
- Produces: `run_calibration(conn, cap, engine, frame_count: int, max_stdev: float) -> bool` — returns `True` on success (baseline saved), `False` if motion was too high (caller should prompt retry).

**Why this is manual-only:** drives a real webcam capture loop; verified by running it and checking the printed prompts/values, not by pytest.

- [ ] **Step 1: Append the capture flow to `posture_guardian/calibration.py`**

```python
import time

from posture_guardian.posture_engine import landmarks_to_metrics


def run_calibration(conn, cap, engine, frame_count: int, max_stdev: float) -> bool:
    print("Sit in your normal, good posture. Capturing in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("Capturing now, hold still...")

    samples = []
    while len(samples) < frame_count:
        ok, frame = cap.read()
        if not ok:
            continue
        landmarks = engine.process_frame(frame)
        if landmarks is None:
            continue
        samples.append(landmarks_to_metrics(landmarks))

    if is_motion_too_high(samples, max_stdev):
        print("Too much movement during calibration. Please hold still and try again.")
        return False

    baseline = average_metrics(samples)
    from posture_guardian import storage

    storage.save_calibration(
        conn,
        neck_angle=baseline.neck_angle,
        shoulder_tilt=baseline.shoulder_tilt,
        forward_lean=baseline.forward_lean,
    )
    print(
        f"Calibration saved: neck_angle={baseline.neck_angle:.1f} "
        f"shoulder_tilt={baseline.shoulder_tilt:.3f} forward_lean={baseline.forward_lean:.3f}"
    )
    return True
```

- [ ] **Step 2: Manual verification**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python -c "
import cv2
from posture_guardian import storage, config
from posture_guardian.posture_engine import PoseEngine
from posture_guardian.calibration import run_calibration

conn = storage.init_db(config.DB_PATH)
cap = cv2.VideoCapture(0)
engine = PoseEngine()
ok = run_calibration(conn, cap, engine, config.CALIBRATION_FRAME_COUNT, config.CALIBRATION_MAX_STDEV)
print('calibration ok:', ok)
cap.release()
engine.close()
"
```

Expected: countdown prints, then "Capturing now, hold still...", then either a saved-baseline line with plausible numbers (`neck_angle` roughly 0-40, `forward_lean` roughly 0.1-0.5) or a "too much movement" message if you moved. Re-run while deliberately moving around to confirm the retry path triggers.

- [ ] **Step 3: Commit**

```bash
git add posture_guardian/calibration.py
git commit -m "Add guided calibration capture flow (manually verified)"
```

---

## Task 8: `alerts.py` — debounce logic

**Files:**
- Create: `posture_guardian/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: nothing (injectable clock for testability).
- Produces: `AlertDebouncer` class with constructor `AlertDebouncer(consecutive_required: int, cooldown_seconds: float, clock=time.monotonic)` and method `update(state: str) -> bool` (returns `True` exactly when an alert should fire).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_alerts.py
from posture_guardian.alerts import AlertDebouncer


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_no_alert_before_consecutive_threshold_reached():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is False


def test_alert_fires_once_threshold_reached():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    debouncer.update("slouching")
    debouncer.update("slouching")
    assert debouncer.update("slouching") is True


def test_alert_does_not_refire_during_cooldown():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    assert debouncer.update("slouching") is False


def test_alert_refires_after_cooldown_elapses():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    clock.advance(61.0)
    assert debouncer.update("slouching") is True


def test_good_state_resets_consecutive_counter():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    debouncer.update("slouching")
    debouncer.update("slouching")
    debouncer.update("good")
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is True


def test_different_states_tracked_independently():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    assert debouncer.update("neck_bent") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_alerts.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `posture_guardian/alerts.py`**

```python
import time


class AlertDebouncer:
    def __init__(self, consecutive_required: int, cooldown_seconds: float, clock=time.monotonic):
        self.consecutive_required = consecutive_required
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._consecutive = {}
        self._last_fired = {}

    def update(self, state: str) -> bool:
        if state == "good":
            self._consecutive.clear()
            return False

        self._consecutive[state] = self._consecutive.get(state, 0) + 1
        if self._consecutive[state] < self.consecutive_required:
            return False

        now = self._clock()
        last = self._last_fired.get(state)
        if last is not None and (now - last) < self.cooldown_seconds:
            return False

        self._last_fired[state] = now
        self._consecutive[state] = 0
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_alerts.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add posture_guardian/alerts.py tests/test_alerts.py
git commit -m "Add debounced alert triggering logic"
```

---

## Task 9: `alerts.py` — overlay window (manual verification)

**Files:**
- Modify: `posture_guardian/alerts.py`

**Interfaces:**
- Consumes: nothing beyond stdlib `tkinter`.
- Produces: `show_overlay(message: str, duration_seconds: float = 4.0) -> None` — spawns a borderless, always-on-top window with `message`, auto-closes after `duration_seconds`.

**Why this is manual-only:** rendering and window behavior (always-on-top, borderless, auto-dismiss) can only be judged by looking at the screen.

- [ ] **Step 1: Append `show_overlay` to `posture_guardian/alerts.py`**

```python
ALERT_MESSAGES = {
    "slouching": "Sit up straight",
    "too_close": "You're too close to the screen",
    "neck_bent": "Straighten your neck",
}


def show_overlay(message: str, duration_seconds: float = 4.0) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    width, height = 340, 90
    screen_width = root.winfo_screenwidth()
    x = (screen_width - width) // 2
    y = 40
    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg="#1e1e1e", bd=2, relief="ridge")
    frame.pack(fill="both", expand=True)

    label = tk.Label(
        frame,
        text=message,
        fg="white",
        bg="#1e1e1e",
        font=("Helvetica", 16, "bold"),
        wraplength=300,
    )
    label.pack(expand=True)

    root.after(int(duration_seconds * 1000), root.destroy)
    root.mainloop()
```

- [ ] **Step 2: Manual verification script**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python -c "
from posture_guardian.alerts import show_overlay, ALERT_MESSAGES
show_overlay(ALERT_MESSAGES['slouching'])
"
```

Expected: a small dark, borderless window titled with "Sit up straight" appears centered near the top of the screen, stays on top of other windows, and disappears on its own after ~4 seconds without needing to be closed manually.

- [ ] **Step 3: Commit**

```bash
git add posture_guardian/alerts.py
git commit -m "Add overlay alert window (manually verified)"
```

---

## Task 10: `tray_app.py` — background detection loop + tray icon (manual verification)

**Files:**
- Create: `posture_guardian/tray_app.py`

**Interfaces:**
- Consumes: `PoseEngine`, `landmarks_to_metrics` (Task 5); `PostureMetrics`, `Thresholds`, `classify_state`, `compute_score` (Task 3); `AlertDebouncer`, `show_overlay`, `ALERT_MESSAGES` (Tasks 8-9); `init_db`, `get_calibration`, `upsert_daily_stats`, `log_event` (Task 2); `run_calibration` (Task 7); constants from `posture_guardian.config` (Task 1).
- Produces: `PostureGuardianApp` class with `start() -> None` (blocks, runs the tray event loop) and `stop() -> None`.

**Why this is manual-only:** integrates camera, tray icon, and threading — end-to-end behavior can only be confirmed by running the app and watching the tray icon/alerts respond to real posture changes.

- [ ] **Step 1: Write `posture_guardian/tray_app.py`**

```python
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
```

- [ ] **Step 2: Manual verification**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python -c "
from posture_guardian.tray_app import PostureGuardianApp
app = PostureGuardianApp()
app.start()
"
```

Expected: a tray icon appears (grey — no calibration yet). Click "Calibrate", follow the countdown, hold good posture. After calibration, the icon turns green while you sit well and red when you slouch/lean in/bend your neck; after ~1.5s of bad posture an overlay alert appears with the matching message and disappears on its own; a second alert for the same problem doesn't reappear for 60 seconds. Click "Pause" and confirm detection stops (icon goes grey, no more alerts) until unpaused. Click "Quit" and confirm the process exits cleanly.

- [ ] **Step 3: Commit**

```bash
git add posture_guardian/tray_app.py
git commit -m "Add tray app wiring detection loop, alerts, and calibration (manually verified)"
```

---

## Task 11: `dashboard.py` — score/history window (manual verification)

**Files:**
- Create: `posture_guardian/dashboard.py`

**Interfaces:**
- Consumes: `get_daily_stats`, `get_recent_stats` from `posture_guardian.storage` (Task 2); `compute_score` from `posture_guardian.scoring` (Task 3).
- Produces: `show_dashboard(conn) -> None` — opens a tkinter window showing today's score and a 7-day history list.

**Why this is manual-only:** rendering is only checkable by looking at the window; there's no headless display in CI to assert against.

- [ ] **Step 1: Write `posture_guardian/dashboard.py`**

```python
import datetime
import tkinter as tk

from posture_guardian.scoring import compute_score
from posture_guardian.storage import get_daily_stats, get_recent_stats


def show_dashboard(conn) -> None:
    today = datetime.date.today().isoformat()
    today_stats = get_daily_stats(conn, today)
    today_score = compute_score(today_stats["good_seconds"], today_stats["monitored_seconds"])
    recent = get_recent_stats(conn, days=7)

    root = tk.Tk()
    root.title("Posture Guardian — Dashboard")
    root.geometry("320x360")

    tk.Label(root, text="Today's Posture Score", font=("Helvetica", 14, "bold")).pack(pady=(16, 4))
    tk.Label(root, text=f"{today_score:.0f}%", font=("Helvetica", 32, "bold")).pack(pady=(0, 16))

    tk.Label(root, text="Last 7 days", font=("Helvetica", 12, "bold")).pack(pady=(8, 4))

    history_frame = tk.Frame(root)
    history_frame.pack(fill="both", expand=True, padx=16)

    for row in recent:
        score = compute_score(row["good_seconds"], row["monitored_seconds"])
        tk.Label(history_frame, text=f"{row['date']}: {score:.0f}%", anchor="w").pack(fill="x")

    root.mainloop()
```

- [ ] **Step 2: Manual verification**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python -c "
from posture_guardian import storage, config
from posture_guardian.dashboard import show_dashboard

conn = storage.init_db(config.DB_PATH)
storage.upsert_daily_stats(conn, '2026-06-30', good_seconds=1800.0, monitored_seconds=2400.0)
show_dashboard(conn)
"
```

Expected: a window titled "Posture Guardian — Dashboard" opens, shows today's score (0% if no data logged yet today) and a line for 2026-06-30 reading "2026-06-30: 75%". Close the window and confirm the process exits.

- [ ] **Step 3: Commit**

```bash
git add posture_guardian/dashboard.py
git commit -m "Add dashboard window showing daily posture score and history (manually verified)"
```

---

## Task 12: `main.py` — entrypoint and full end-to-end smoke test

**Files:**
- Create: `posture_guardian/main.py`

**Interfaces:**
- Consumes: `PostureGuardianApp` from `posture_guardian.tray_app` (Task 10).
- Produces: module runnable via `python -m posture_guardian.main`.

- [ ] **Step 1: Write `posture_guardian/main.py`**

```python
from posture_guardian.tray_app import PostureGuardianApp


def main() -> None:
    app = PostureGuardianApp()
    app.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full automated test suite**

```bash
cd /Users/ranjana/Harsha/Projects/posture
pytest -v
```

Expected: all tests from Tasks 2, 3, 4, 6, 8 pass (22 tests total), 0 failures.

- [ ] **Step 3: End-to-end manual smoke test**

```bash
cd /Users/ranjana/Harsha/Projects/posture
python -m posture_guardian.main
```

Expected: tray icon appears grey; Calibrate → countdown → baseline saved; sit well → icon green; slouch/lean in/bend neck for ~2s → icon red + overlay alert with correct message; open Show Dashboard → today's score reflects the last few minutes; Pause → icon greys out and stays inert; Quit → process exits, no lingering camera light.

- [ ] **Step 4: Commit**

```bash
git add posture_guardian/main.py
git commit -m "Add entrypoint; posture guardian MVP complete"
```

---

## Self-Review Notes

- **Spec coverage:** detection (Tasks 4-5), calibration (Tasks 6-7), scoring/score math (Task 3), debounced alerts + overlay (Tasks 8-9), SQLite storage (Task 2), tray app + pause/quit (Task 10), dashboard (Task 11), error handling for no-camera/no-person/calibration-motion (built into Tasks 7 and 10), entrypoint (Task 12) — all spec sections have a corresponding task.
- **Automated vs. manual split matches spec Testing section exactly:** `scoring.py`, `storage.py`, plus the two additional pure modules identified during planning (`posture_engine.landmarks_to_metrics` geometry and `calibration`'s averaging/motion-check) are unit-tested; camera/tray/overlay/dashboard code is manually verified and each such task states why.
- **Type/signature consistency checked:** `PostureMetrics`/`Thresholds` defined once in `scoring.py` and reused unchanged by `posture_engine.py`, `calibration.py`, `tray_app.py`; `PoseLandmarks`/`Landmark` defined once in `posture_engine.py` and reused by `calibration.py`; `AlertDebouncer.update` and `show_overlay`/`ALERT_MESSAGES` signatures match their use in `tray_app.py`; `storage` function names/signatures match between Task 2 and their callers in Tasks 7, 10, 11.
