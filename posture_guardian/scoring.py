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
