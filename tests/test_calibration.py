import pytest

from posture_guardian.scoring import PostureMetrics
from posture_guardian.calibration import average_metrics, is_motion_too_high


def test_average_metrics_computes_mean_of_each_field():
    samples = [
        PostureMetrics(neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2),
        PostureMetrics(neck_angle=20.0, shoulder_tilt=2.0, forward_lean=0.4),
    ]
    avg = average_metrics(samples)
    expected = PostureMetrics(neck_angle=15.0, shoulder_tilt=1.5, forward_lean=0.3)
    assert avg.neck_angle == pytest.approx(expected.neck_angle)
    assert avg.shoulder_tilt == pytest.approx(expected.shoulder_tilt)
    assert avg.forward_lean == pytest.approx(expected.forward_lean)


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
