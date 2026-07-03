import time
from statistics import mean, pstdev

from posture_guardian.posture_engine import landmarks_to_metrics
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


def run_calibration(conn, cap, engine, frame_count: int, max_stdev: float, timeout_seconds: float = 30.0) -> bool:
    print("Sit in your normal, good posture. Capturing in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("Capturing now, hold still...")

    samples = []
    deadline = time.monotonic() + timeout_seconds
    while len(samples) < frame_count:
        if time.monotonic() > deadline:
            print("Calibration timed out — camera produced no usable frames. Please try again.")
            return False
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
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
