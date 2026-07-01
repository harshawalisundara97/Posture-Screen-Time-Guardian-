# Posture & Screen-Time Guardian — Design Spec

Date: 2026-07-01
Status: Approved

## Summary

A macOS desktop app (Python) that watches posture via webcam using MediaPipe Pose,
alerts the user in real time when they slouch, lean too close to the screen, or bend
their neck, and tracks a daily posture score. Runs as a system tray app with no
persistent camera preview window. MVP is local-only; a FastAPI backend / web dashboard
/ Flutter companion ("PostureGuard for remote workers") is an explicit future step, not
part of this build.

## Goals (MVP)

- Detect three posture problems from webcam pose landmarks: slouching, leaning too
  close to the screen, and excessive neck bend.
- Alert via an on-screen overlay window when a problem persists (debounced, not
  per-frame).
- Calibrate to the individual user on first run (guided baseline capture), rather than
  using fixed generic thresholds.
- Track daily posture score (% of monitored time in good posture) and store history
  locally in SQLite.
- Run unobtrusively as a system tray app — no visible camera feed during normal use.

## Non-goals (MVP)

- No cloud backend, accounts, or sync (that's the later SaaS phase).
- No Windows/Linux packaging effort — target macOS first.
- No screen-time tracking (despite the project name) — posture only for MVP.
- No camera preview / skeleton overlay UI — headless detection only.

## Architecture

Single Python process, three concurrent pieces:

- **Detection loop** (background thread): OpenCV captures webcam frames, MediaPipe
  Pose extracts landmarks, metrics are computed each frame and compared to the
  calibrated baseline. State changes are pushed onto a thread-safe queue.
- **Tray app** (main thread, `pystray`): status icon (green = good, red = bad, grey =
  no camera/paused). Menu: Calibrate, Show Dashboard, Pause, Quit.
- **Overlay window** (`tkinter`, spawned on demand): borderless, always-on-top,
  auto-dismisses after a few seconds. Shows the specific nudge, e.g. "Sit up
  straight", "You're too close to the screen", "Straighten your neck".

SQLite stores the calibration baseline and per-day aggregated posture stats. A
separate lightweight dashboard window (tkinter, opened from the tray menu) reads from
SQLite to show today's score and a short trend.

## Components

- `posture_engine.py` — MediaPipe Pose wrapper. Given a frame, returns landmark-derived
  metrics: neck angle, shoulder tilt, forward-lean distance estimate.
- `calibration.py` — guided baseline capture (countdown + N frames averaged while user
  sits in good posture), writes baseline to SQLite. Discards and retries the sample if
  motion during capture is too high.
- `scoring.py` — pure functions: given current metrics + baseline + config thresholds,
  return posture state (`good` / `slouching` / `too_close` / `neck_bent` /
  `unmonitored`) and update running daily time-in-state totals. No I/O, no camera
  dependency — fully unit-testable.
- `alerts.py` — debounced alert logic: requires N consecutive bad frames before firing,
  then applies a cooldown before the same alert can fire again. Triggers the tkinter
  overlay.
- `tray_app.py` — pystray icon + menu wiring; owns/starts the background detection
  thread.
- `dashboard.py` — tkinter window rendering today's score (%) and a 7-day mini history,
  reading from SQLite.
- `storage.py` — SQLite schema + read/write helpers: `calibration` table (one row per
  user baseline), `daily_stats` table (date, good_seconds, monitored_seconds), `events`
  table (timestamp, state) kept for debugging/tuning thresholds.
- `main.py` — entrypoint; loads config, wires components together, starts tray app.

## Data flow

1. Webcam frame → MediaPipe Pose landmarks.
2. `posture_engine` computes metrics (neck angle, shoulder tilt, forward-lean
   distance).
3. `scoring` compares metrics to the calibrated baseline + configured thresholds →
   posture state.
4. If body/face isn't detected, state is `unmonitored`: not counted as bad posture, no
   alert fires, tray icon shows a neutral/grey state.
5. Debounced bad states are handed to `alerts`, which shows the overlay with a specific
   message.
6. Every N seconds, accumulated per-state durations are flushed to SQLite
   `daily_stats` (upsert on the current date).
7. Daily score = `good_seconds / monitored_seconds * 100`, shown in `dashboard.py`.

## Calibration flow

On first run (or via tray menu "Calibrate"):

1. Tray shows a short countdown prompt asking the user to sit in their normal, good
   posture.
2. App captures N frames (a few seconds) once the countdown ends.
3. If motion across those frames exceeds a sanity threshold (user wasn't still), the
   sample is discarded and the user is asked to redo it.
4. Otherwise, the averaged metrics (neck angle, shoulder tilt, forward-lean distance)
   are written to SQLite as the baseline for that user.
5. All subsequent scoring compares live metrics against this baseline plus a
   configurable sensitivity margin.

## Error handling

- No webcam / webcam busy: tray icon shows a distinct "no camera" state, retries on an
  interval, never crashes the app.
- No person detected in frame (stepped away): treated as `unmonitored`, doesn't count
  toward score, doesn't trigger alerts.
- Calibration cancelled or too much motion: discard the sample, prompt user to redo
  calibration; app keeps running with no baseline (skips scoring) until calibration
  succeeds.

## Testing

- Unit tests (run in CI, no camera required):
  - `scoring.py` — feed synthetic landmark angles/baselines, assert correct posture
    state classification and score accumulation math.
  - `storage.py` — SQLite read/write round-trip for calibration and daily_stats.
- Manual verification only (not automatable): `posture_engine.py` (real MediaPipe
  output against a real webcam), `tray_app.py`, `alerts.py` overlay appearance, and
  `dashboard.py` rendering. This is called out explicitly rather than faking coverage
  with mocked camera input.

## Tech stack

- Python 3.11+
- `opencv-python` — webcam capture
- `mediapipe` — Pose landmark detection
- `pystray` + `Pillow` — system tray icon/menu
- `tkinter` (stdlib) — overlay + dashboard windows
- `sqlite3` (stdlib) — local storage

## Future work (explicitly out of scope for this spec)

- FastAPI backend receiving pose keypoints or aggregated stats, for multi-device sync
  and history beyond local SQLite.
- Web dashboard for daily/weekly stats.
- Flutter companion app showing daily stats on mobile.
- Screen-time tracking alongside posture.
- Windows/Linux support.
- "PostureGuard for remote workers" SaaS packaging (subscriptions, multi-user, teams).
