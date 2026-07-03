import math
from dataclasses import dataclass
from pathlib import Path

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


# BlazePose 33-point topology (stable across MediaPipe's legacy Solutions API
# and the newer Tasks API): 0=nose, 7=left ear, 8=right ear, 11=left shoulder,
# 12=right shoulder.
_NOSE, _LEFT_EAR, _RIGHT_EAR, _LEFT_SHOULDER, _RIGHT_SHOULDER = 0, 7, 8, 11, 12

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
_MODEL_PATH = Path.home() / ".posture_guardian" / "pose_landmarker_lite.task"


def _ensure_model() -> Path:
    if not _MODEL_PATH.exists():
        import ssl
        import urllib.request

        import certifi

        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = _MODEL_PATH.with_suffix(".task.download")
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(_MODEL_URL, context=ssl_context) as response:
            tmp_path.write_bytes(response.read())
        tmp_path.rename(_MODEL_PATH)
    return _MODEL_PATH


class PoseEngine:
    """Wraps MediaPipe's Pose Landmarker (Tasks API) for a live webcam feed.

    Manual-verification only — see Task 5 of the plan. Uses the Tasks API
    rather than the legacy `mp.solutions.pose` because current MediaPipe
    wheels no longer ship the Solutions API on this platform.
    """

    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(_ensure_model())),
            running_mode=vision.RunningMode.IMAGE,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._mp = mp
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def process_frame(self, frame_bgr):
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)

        if not result.pose_landmarks:
            return None

        lm = result.pose_landmarks[0]

        def pt(landmark_id):
            p = lm[landmark_id]
            return Landmark(x=p.x, y=p.y)

        return PoseLandmarks(
            nose=pt(_NOSE),
            left_shoulder=pt(_LEFT_SHOULDER),
            right_shoulder=pt(_RIGHT_SHOULDER),
            left_ear=pt(_LEFT_EAR),
            right_ear=pt(_RIGHT_EAR),
        )

    def close(self):
        self._landmarker.close()
