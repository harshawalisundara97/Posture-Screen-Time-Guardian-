import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS calibration (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    neck_angle REAL NOT NULL,
    shoulder_tilt REAL NOT NULL,
    forward_lean REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    good_seconds REAL NOT NULL DEFAULT 0,
    monitored_seconds REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    state TEXT NOT NULL
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_calibration(conn: sqlite3.Connection, neck_angle: float, shoulder_tilt: float, forward_lean: float) -> None:
    conn.execute(
        """
        INSERT INTO calibration (id, neck_angle, shoulder_tilt, forward_lean)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            neck_angle = excluded.neck_angle,
            shoulder_tilt = excluded.shoulder_tilt,
            forward_lean = excluded.forward_lean
        """,
        (neck_angle, shoulder_tilt, forward_lean),
    )
    conn.commit()


def get_calibration(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute(
        "SELECT neck_angle, shoulder_tilt, forward_lean FROM calibration WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    return {"neck_angle": row[0], "shoulder_tilt": row[1], "forward_lean": row[2]}


def upsert_daily_stats(conn: sqlite3.Connection, date: str, good_seconds: float, monitored_seconds: float) -> None:
    conn.execute(
        """
        INSERT INTO daily_stats (date, good_seconds, monitored_seconds)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            good_seconds = daily_stats.good_seconds + excluded.good_seconds,
            monitored_seconds = daily_stats.monitored_seconds + excluded.monitored_seconds
        """,
        (date, good_seconds, monitored_seconds),
    )
    conn.commit()


def get_daily_stats(conn: sqlite3.Connection, date: str) -> dict:
    row = conn.execute(
        "SELECT good_seconds, monitored_seconds FROM daily_stats WHERE date = ?", (date,)
    ).fetchone()
    if row is None:
        return {"good_seconds": 0.0, "monitored_seconds": 0.0}
    return {"good_seconds": row[0], "monitored_seconds": row[1]}


def get_recent_stats(conn: sqlite3.Connection, days: int) -> list[dict]:
    rows = conn.execute(
        "SELECT date, good_seconds, monitored_seconds FROM daily_stats ORDER BY date DESC LIMIT ?",
        (days,),
    ).fetchall()
    return [{"date": r[0], "good_seconds": r[1], "monitored_seconds": r[2]} for r in rows]


def log_event(conn: sqlite3.Connection, timestamp: str, state: str) -> None:
    conn.execute("INSERT INTO events (timestamp, state) VALUES (?, ?)", (timestamp, state))
    conn.commit()
