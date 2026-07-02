from statistics import mean, pstdev

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
