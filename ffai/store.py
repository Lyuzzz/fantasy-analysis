# ==============================================================================
# store.py - SQLite state: which alerts were already sent, plus small flags
#
# Flow (SPEC 6.1), same shape as stock-ai's news gate:
#   is_sent(key)    read-only check, safe to call any time
#   ... notify ...
#   mark_sent(alert) called ONLY after at least one channel delivered it.
# If every channel fails we skip mark_sent, so the next check retries.
#
# Uses the stdlib sqlite3 module (no ORM). All timestamps are UTC.
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
    # settings.db_path is read on every call (not at import) so tests can
    # point it at a temp file.
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)  # IF NOT EXISTS: cheap, and no separate init step
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
    """Record an alert as sent. Returns True only if the key was new."""
    try:
        with _session() as conn:
            conn.execute(
                "INSERT INTO sent_alerts (key, kind, week, title, sent_at) VALUES (?, ?, ?, ?, ?)",
                (alert.key, alert.kind, alert.week, alert.title, _now()),
            )
        return True
    except sqlite3.IntegrityError:
        return False  # already recorded (a second run, or a retry after a crash)


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
