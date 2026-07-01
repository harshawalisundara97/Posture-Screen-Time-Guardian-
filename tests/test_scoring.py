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
