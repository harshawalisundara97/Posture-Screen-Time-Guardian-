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
