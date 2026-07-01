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
