import pytest
from posture_guardian import storage


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    return storage.init_db(db_path)


def test_calibration_round_trip(conn):
    assert storage.get_calibration(conn) is None
    storage.save_calibration(conn, neck_angle=12.5, shoulder_tilt=1.2, forward_lean=0.3)
    baseline = storage.get_calibration(conn)
    assert baseline == {"neck_angle": 12.5, "shoulder_tilt": 1.2, "forward_lean": 0.3}


def test_save_calibration_overwrites_previous(conn):
    storage.save_calibration(conn, neck_angle=10.0, shoulder_tilt=1.0, forward_lean=0.2)
    storage.save_calibration(conn, neck_angle=20.0, shoulder_tilt=2.0, forward_lean=0.4)
    baseline = storage.get_calibration(conn)
    assert baseline == {"neck_angle": 20.0, "shoulder_tilt": 2.0, "forward_lean": 0.4}


def test_daily_stats_accumulate(conn):
    storage.upsert_daily_stats(conn, "2026-07-01", good_seconds=10.0, monitored_seconds=15.0)
    storage.upsert_daily_stats(conn, "2026-07-01", good_seconds=5.0, monitored_seconds=5.0)
    stats = storage.get_daily_stats(conn, "2026-07-01")
    assert stats == {"good_seconds": 15.0, "monitored_seconds": 20.0}


def test_daily_stats_missing_date_returns_zeros(conn):
    stats = storage.get_daily_stats(conn, "2026-01-01")
    assert stats == {"good_seconds": 0.0, "monitored_seconds": 0.0}


def test_recent_stats_ordered_desc_and_limited(conn):
    storage.upsert_daily_stats(conn, "2026-06-28", good_seconds=1.0, monitored_seconds=2.0)
    storage.upsert_daily_stats(conn, "2026-06-29", good_seconds=1.0, monitored_seconds=2.0)
    storage.upsert_daily_stats(conn, "2026-06-30", good_seconds=1.0, monitored_seconds=2.0)
    recent = storage.get_recent_stats(conn, days=2)
    assert [r["date"] for r in recent] == ["2026-06-30", "2026-06-29"]


def test_log_event_inserts_row(conn):
    storage.log_event(conn, timestamp="2026-07-01T10:00:00", state="slouching")
    row = conn.execute("SELECT timestamp, state FROM events").fetchone()
    assert row == ("2026-07-01T10:00:00", "slouching")
