# ==============================================================================
# store.py: SQLite state. It records which alerts the program sent.
# It also holds small flags.
#
# The flow (SPEC 6.1) has the same shape as the news gate in stock-ai:
#   is_sent(key)      reads only. The caller can use it at any time.
#   ... notify ...
#   mark_sent(alert)  runs ONLY after at least one channel delivered the alert.
# When every channel fails, the caller skips mark_sent. The next check then retries.
#
# The module uses the sqlite3 module of the standard library. It uses no ORM.
# All timestamps are UTC.
# ==============================================================================
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ffai.config import settings
from ffai.models import Alert

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sent_alerts (
    key      TEXT PRIMARY KEY,
    kind     TEXT NOT NULL,
    league_id TEXT NOT NULL DEFAULT '',
    week     INTEGER,
    title    TEXT NOT NULL,
    sent_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""


@contextmanager
def _session() -> Iterator[sqlite3.Connection]:
    # The function reads settings.db_path on every call, not at import.
    # A test can then point it at a temporary file.
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)  # IF NOT EXISTS is cheap and removes the need for a separate init step
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_sent(key: str) -> bool:
    with _session() as conn:
        row = conn.execute("SELECT 1 FROM sent_alerts WHERE key = ?", (key,)).fetchone()
    return row is not None


def mark_sent(alert: Alert) -> bool:
    """Record an alert as sent. Return True only if the key is new."""
    try:
        with _session() as conn:
            conn.execute(
                "INSERT INTO sent_alerts (key, kind, league_id, week, title, sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                (alert.key, alert.kind, alert.league_id, alert.week, alert.title, _now()),
            )
        return True
    except sqlite3.IntegrityError:
        return False  # The key exists already (a second run, or a retry after a crash).


def get_kv(key: str, default: str | None = None) -> str | None:
    with _session() as conn:
        row = conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
    return row[0] if row else default


def set_kv(key: str, value: str) -> None:
    with _session() as conn:
        conn.execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (key, value),
        )
