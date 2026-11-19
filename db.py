"""SQLite storage layer."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import config

COLUMNS = [
    "city", "observed_at", "temperature", "apparent_temp", "humidity",
    "precipitation", "wind_speed", "us_aqi", "pm2_5", "pm10",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    city          TEXT NOT NULL,
    observed_at   TEXT NOT NULL,
    temperature   REAL,
    apparent_temp REAL,
    humidity      REAL,
    precipitation REAL,
    wind_speed    REAL,
    us_aqi        REAL,
    pm2_5         REAL,
    pm10          REAL,
    PRIMARY KEY (city, observed_at)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    city       TEXT NOT NULL,
    status     TEXT NOT NULL,
    message    TEXT
);
"""


@contextmanager
def get_conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_readings(rows):
    if not rows:
        return
    sql = (
        f"INSERT OR REPLACE INTO readings ({', '.join(COLUMNS)}) "
        f"VALUES ({', '.join('?' for _ in COLUMNS)})"
    )
    data = [tuple(r.get(c) for c in COLUMNS) for r in rows]
    with get_conn() as conn:
        conn.executemany(sql, data)


def log_fetch(city, status, message=""):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fetch_log (fetched_at, city, status, message) VALUES (?, ?, ?, ?)",
            (now, city, status, message),
        )


def count_readings(city=None):
    with get_conn() as conn:
        if city:
            cur = conn.execute("SELECT COUNT(*) FROM readings WHERE city = ?", (city,))
        else:
            cur = conn.execute("SELECT COUNT(*) FROM readings")
        return cur.fetchone()[0]


def last_fetch(status=None):
    """Latest fetch time (UTC, timezone-aware) or None."""
    with get_conn() as conn:
        if status:
            cur = conn.execute("SELECT MAX(fetched_at) FROM fetch_log WHERE status = ?", (status,))
        else:
            cur = conn.execute("SELECT MAX(fetched_at) FROM fetch_log")
        value = cur.fetchone()[0]
    return datetime.fromisoformat(value) if value else None


def read_readings(hours):
    cutoff = (datetime.now(ZoneInfo(config.TIMEZONE)) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM readings WHERE observed_at >= ? ORDER BY observed_at",
            conn,
            params=(cutoff,),
        )
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    return df


def read_log(limit=50):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT fetched_at, city, status, message FROM fetch_log ORDER BY id DESC LIMIT ?",
            conn,
            params=(limit,),
        )