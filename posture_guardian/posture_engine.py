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
