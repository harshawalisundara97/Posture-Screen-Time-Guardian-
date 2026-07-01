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
