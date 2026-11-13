"""Persistent, offline-only recovery observations for an UNVERIFIED XAU status file.

This does not validate a licensed market feed or grant any paper/live trades.
A local snapshot can be synthetic or injected. Even repeated fresh snapshots
can NEVER arm a trade, a research engine, notifications, or vendor access.
"""
from __future__ import annotations
import datetime as dt
import os
import pathlib
import sqlite3
import stat

from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
REQUIRED_OBSERVATIONS = 3
MIN_SEPARATION_SECONDS = 30
MAX_SEPARATION_SECONDS = 120
MAX_SUMMARY_AGE_SECONDS = 120
SOURCE_STATES = {
    "NOT_CONNECTED": "SOURCE_ABSENT",
    "BLOCKED": "SOURCE_REJECTED",
    "WAIT_STALE": "SOURCE_INTERRUPTED",
    "WAIT_NO_VERIFIED_QUOTE": "SOURCE_INTERRUPTED",
    "WAIT_REVIEW_OBSERVATION_ONLY": "OBSERVATION_SEEN_UNVERIFIED",
}
PUBLIC_STATES = set(SOURCE_STATES.values()) | {
    "OBSERVATION_REPEATED_UNVERIFIED", "RECOVERY_DISABLED",
    "RECOVERY_NOT_STARTED", "RECOVERY_UNAVAILABLE", "RECOVERY_STALE"
}


def _time(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime):
        raise ValueError("datetime required")
    return parse_utc(value.isoformat())


def _iso(value: dt.datetime) -> str:
    return _time(value).isoformat().replace("+00:00", "Z")


def disabled_recovery() -> dict:
    return _base("RECOVERY_DISABLED")


def _base(state: str) -> dict:
    return {"state": state, "consecutiveObservations": 0,
            "requiredObservations": REQUIRED_OBSERVATIONS,
            "lastObservedUTC": None, "transitionCount": 0,
            "sourceVerified": False, "paperOrdersAllowed": False,
            "signal": "WAIT", "executable": False}


def _classify(result: object) -> str:
    # Never use a caller-provided "ready", "BUY", "approved" or paper flag.
    if not isinstance(result, dict) or result.get("status") != "WAIT_EODHD_INTAKE":
        return "SOURCE_REJECTED"
    if (result.get("signal") != "WAIT" or result.get("executable") is not False
            or result.get("researchEligible") is not False
            or result.get("paperRunning") is not False
            or result.get("engineStatus") != "NOT_INVOKED"
            or result.get("sourceRequestsMade") != 0):
        return "SOURCE_REJECTED"
    data_status = result.get("dataStatus")
    return SOURCE_STATES.get(data_status, "SOURCE_REJECTED")


def observe_recovery(database: str | pathlib.Path, result: object,
                     now: dt.datetime) -> dict:
    """One atomic state transition, with restart-safe debouncing and UTC guard."""
    stamp = _time(now)
    path = pathlib.Path(database)
    if path.is_symlink():
        raise ValueError("Recovery database cannot be symlinked")
    if path.exists():
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Recovery database must be regular")
    label = _classify(result)
    db = sqlite3.connect(path, isolation_level=None, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS private_feed_recovery(
            id INTEGER PRIMARY KEY CHECK(id=1),
            state TEXT NOT NULL,
            classification TEXT NOT NULL,
            streak INTEGER NOT NULL,
            last_tick_utc TEXT NOT NULL,
            transitions INTEGER NOT NULL
        )""")
        db.execute("BEGIN IMMEDIATE")
        try:
            old = db.execute("SELECT * FROM private_feed_recovery WHERE id=1").fetchone()
            streak = 0
            transitions = 0 if old is None else old["transitions"]
            if old is not None:
                prev = parse_utc(old["last_tick_utc"])
                delta = (stamp - prev).total_seconds()
                if delta < 0:
                    raise ValueError("Recovery clock moved backwards")
                if delta == 0 and old["classification"] != label:
                    raise ValueError("Conflicting classification for the same tick")
                if delta == 0:
                    db.execute("COMMIT")
                    return _summary(old["state"], old["streak"],
                                    old["last_tick_utc"], transitions)
            else:
                delta = None
            if label == "OBSERVATION_SEEN_UNVERIFIED":
                if (old is not None and old["classification"] == label
                        and MIN_SEPARATION_SECONDS <= delta <= MAX_SEPARATION_SECONDS):
                    streak = min(REQUIRED_OBSERVATIONS, old["streak"] + 1)
                else:
                    streak = 1
                state = ("OBSERVATION_REPEATED_UNVERIFIED" if streak >= REQUIRED_OBSERVATIONS
                         else "OBSERVATION_SEEN_UNVERIFIED")
            else:
                state = label
            if old is not None and state != old["state"]:
                transitions = min(transitions + 1, 1_000_000)
            db.execute("""INSERT INTO private_feed_recovery
                 (id,state,classification,streak,last_tick_utc,transitions)
                 VALUES (1,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET state=excluded.state,
                 classification=excluded.classification,streak=excluded.streak,
                 last_tick_utc=excluded.last_tick_utc,transitions=excluded.transitions""",
                 (state, label, streak, _iso(stamp), transitions))
            db.execute("COMMIT")
            return _summary(state, streak, _iso(stamp), transitions)
        except Exception:
            db.execute("ROLLBACK")
            raise
    finally:
        db.close()
        # SQLite default file mode may inherit permissive process umask.
        # Tighten the recovery DB and sidecar files even when called standalone,
        # not just when the private watchdog manages its 0700 directory.
        for suffix in ("", "-wal", "-shm"):
            candidate = path.with_name(path.name + suffix)
            try:
                info = candidate.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("Unsafe recovery SQLite file")
                candidate.chmod(0o600)
            except FileNotFoundError:
                continue


def _summary(state, streak, last, count) -> dict:
    if (state not in PUBLIC_STATES or not isinstance(streak, int)
            or not 0 <= streak <= REQUIRED_OBSERVATIONS
            or not isinstance(count, int) or not 0 <= count <= 1_000_000):
        raise ValueError("Unsafe recovery summary")
    return {**_base(state), "consecutiveObservations": streak,
            "lastObservedUTC": last, "transitionCount": count}


def read_recovery(database: str | pathlib.Path, now: dt.datetime) -> dict:
    """Read-only, never creates SQLite files, fail-closed for stale/corrupt state."""
    instant = _time(now)
    path = pathlib.Path(database)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return _base("RECOVERY_NOT_STARTED")
    except OSError:
        return _base("RECOVERY_UNAVAILABLE")
    if (not stat.S_ISREG(st.st_mode) or (stat.S_IMODE(st.st_mode) & 0o077)
            or st.st_uid != os.getuid()):
        return _base("RECOVERY_UNAVAILABLE")
    try:
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True,
                             timeout=2)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA query_only=ON")
            row = db.execute("SELECT * FROM private_feed_recovery WHERE id=1").fetchone()
        finally:
            db.close()
        if row is None or row["state"] not in PUBLIC_STATES:
            return _base("RECOVERY_UNAVAILABLE")
        tick = parse_utc(row["last_tick_utc"])
        age = (instant - tick).total_seconds()
        if age < 0:
            return _base("RECOVERY_UNAVAILABLE")
        if age > MAX_SUMMARY_AGE_SECONDS:
            return _base("RECOVERY_STALE")
        return _summary(row["state"], row["streak"], _iso(tick),
                        row["transitions"])
    except (OSError, ValueError, TypeError, IndexError, KeyError, sqlite3.Error):
        return _base("RECOVERY_UNAVAILABLE")
