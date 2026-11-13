"""Offline periodic EODHD private-status audit. No provider or trade engine calls.

A running coordinator may enable this *research-only* process via
PRIVATE_REVIEW_AUDIT_ENABLED=1. Each tick reads ONLY a local private snapshot,
persists deduplicated alert/notification transitions to SQLite, and records a
heartbeat. It NEVER fetches market data, trades, starts paper trading or
sends messages.
"""
from __future__ import annotations
import datetime as dt
import os
from pathlib import Path
import re
import sqlite3
import stat

from eodhd_review_monitor import observe_once
from research_monitor import ResearchAlertMonitor
from private_feed_recovery import observe_recovery,read_recovery,disabled_recovery
from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
FOLDER = "review-audit"
ALERT_DB = "alerts.sqlite3"
NOTICE_DB = "notifications.sqlite3"
RECOVERY_DB = "source-recovery.sqlite3"
INTERVAL_SECONDS = 60
CODES = re.compile(r"[A-Z0-9_]{3,90}\Z")
VALID_STATES = {"AUDIT_DISABLED", "AUDIT_NOT_STARTED", "AUDIT_OK",
                "AUDIT_STALE", "AUDIT_UNAVAILABLE"}


def _is_private_folder(base: Path) -> bool:
    """Reject symbolic links and group/world access on our dedicated audit dir."""
    try:
        info = os.lstat(base)
        return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and not (stat.S_IMODE(info.st_mode) & 0o077))
    except OSError:
        return False


def _folder(data_dir, create=False) -> Path | None:
    root = Path(data_dir)
    folder = root / FOLDER
    if create:
        if folder.is_symlink():
            raise ValueError("Audit path cannot be a symlink")
        folder.mkdir(mode=0o700, exist_ok=True)
    if not _is_private_folder(folder):
        if create:
            raise ValueError("Audit directory must be private, local and owned")
        return None
    return folder


def _db_readonly(path: Path):
    """Read only existing regular SQLite files; do not create files on GET."""
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Unsafe SQLite file")
    # URI is created from a resolved file only after a no-follow lstat.
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def disabled_state() -> dict:
    return {"status": "AUDIT_DISABLED", "lastObservedUTC": None,
            "ageSeconds": None, "alertCodes": [],
            "lastNotificationCode": None, "signal": "WAIT",
            "executable": False, "paperRunning": False,
            "externalNotificationsSent": 0,
            "recovery": disabled_recovery()}


def audit_once(data_dir, now: dt.datetime | None = None) -> dict:
    """Exactly one on-disk audit. Never evaluate market trades."""
    instant = parse_utc((now or dt.datetime.now(UTC)).isoformat())
    directory = _folder(data_dir, create=True)
    alerts = directory / ALERT_DB
    notices = directory / NOTICE_DB
    observed = observe_once(data_dir, alerts, notices, instant)
    if (observed["signal"] != "WAIT" or observed["executable"] is not False
            or observed["result"]["sourceRequestsMade"] != 0
            or observed["result"]["paperRunning"] is not False
            or observed["result"]["engineStatus"] != "NOT_INVOKED"
            or observed["notifications"]["current"]["signal"] != "WAIT"):
        raise RuntimeError("Research-only audit contract blocked")
    # Record only the local WAIT observation; never claim genuine feed recovery.
    observe_recovery(directory / RECOVERY_DB, observed["result"], instant)
    # Persist the previous-cycle interval for a watchdog heartbeat.
    monitor = ResearchAlertMonitor(alerts)
    try:
        monitor.heartbeat_gap_seconds(instant)
    finally:
        monitor.close()
    # SQLite DB is stored in a private 0700 folder and kept 0600.
    for file in directory.iterdir():
        if file.name.startswith((ALERT_DB, NOTICE_DB, RECOVERY_DB)) and file.is_file() and not file.is_symlink():
            file.chmod(0o600)
    return read_audit_state(data_dir, instant, enabled=True)


def read_audit_state(data_dir, now: dt.datetime | None = None, *, enabled=False) -> dict:
    """Bounded read-only summary for authenticated status response. No raw quotes."""
    if not enabled:
        return disabled_state()
    instant = parse_utc((now or dt.datetime.now(UTC)).isoformat())
    base = _folder(data_dir, create=False)
    if base is None:
        return {**disabled_state(), "status": "AUDIT_NOT_STARTED",
                "recovery": read_recovery(base / RECOVERY_DB, instant) if base else
                {**disabled_recovery(), "state": "RECOVERY_NOT_STARTED"}}
    try:
        with _db_readonly(base / ALERT_DB) as db:
            heartbeat = db.execute(
                "SELECT last_heartbeat_utc FROM research_monitor_runtime WHERE id=1"
            ).fetchone()
            alerts = db.execute(
                "SELECT code FROM research_alert_state WHERE active=1 ORDER BY code LIMIT 20"
            ).fetchall()
        with _db_readonly(base / NOTICE_DB) as db:
            notification = db.execute(
                "SELECT state_key FROM research_notification_state WHERE id=1"
            ).fetchone()
        if heartbeat is None:
            return {**disabled_state(), "status": "AUDIT_NOT_STARTED"}
        observed = parse_utc(heartbeat[0])
        delta = int((instant - observed).total_seconds())
        if delta < 0:
            raise ValueError("Audit clock has moved backward")
        safe_codes = []
        for record in alerts:
            code = record[0]
            if isinstance(code, str) and CODES.fullmatch(code):
                safe_codes.append(code)
            else:
                raise ValueError("Untrusted alert code")
        notice_code = None
        if notification is not None:
            parts = notification[0].split(":")
            if len(parts) != 3 or parts[0] not in {"DATA_ALERT", "STATUS", "RESEARCH_SIGNAL"}:
                raise ValueError("Invalid notification code")
            if parts[1] != "WAIT" or not CODES.fullmatch(parts[2]):
                raise ValueError("Unexpected notification signal")
            notice_code = parts[2]
        return {"status": "AUDIT_OK" if delta <= 2 * INTERVAL_SECONDS else "AUDIT_STALE",
                "lastObservedUTC": observed.isoformat().replace("+00:00", "Z"),
                "ageSeconds": delta, "alertCodes": safe_codes,
                "lastNotificationCode": notice_code,
                "signal": "WAIT", "executable": False, "paperRunning": False,
                "externalNotificationsSent": 0,
                "recovery": read_recovery(base / RECOVERY_DB, instant)}
    except (OSError, ValueError, TypeError, sqlite3.Error, IndexError, AttributeError):
        return {**disabled_state(), "status": "AUDIT_UNAVAILABLE",
                "recovery": {**disabled_recovery(), "state": "RECOVERY_UNAVAILABLE"}}


def run_until_stopped(data_dir, stop, *, seconds=INTERVAL_SECONDS, clock=None) -> None:
    """One bounded-in-memory, stoppable thread. No subprocess/provider/network."""
    if not 30 <= seconds <= 3600:
        raise ValueError("Audit interval outside safe range")
    if clock is None:
        clock = lambda: dt.datetime.now(UTC)
    while not stop.is_set():
        try:
            audit_once(data_dir, clock())
        except Exception:
            # Fail closed; retry on next tick without printing sensitive files.
            pass
        if stop.wait(seconds):
            break
