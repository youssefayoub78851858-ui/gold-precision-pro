"""Build fail-closed Research Only notification payloads; never sends them."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3

from xauusd_feed_gate import parse_utc


def build_notification(result: dict | None) -> dict:
    """Format a local preview for a later authorized transport.

    BUY/SELL can only represent an eligible research candidate. The public
    signal stays WAIT and executable is always false. Synthetic, blocked,
    unavailable, malformed, or unverified observations can only report WAIT.
    This module has no network, email, push, or messaging transport.
    """
    if not isinstance(result, dict):
        return _payload("DATA_ALERT", "WAIT", "PIPELINE_UNAVAILABLE",
                        "No pipeline observation was received")

    status = result.get("status")
    intake = result.get("intake") if isinstance(result.get("intake"), dict) else {}
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    alert_blockers = (diagnostics.get("alerts") or {}).get("items", [])
    blocking = next((item for item in alert_blockers
                     if isinstance(item, dict) and item.get("severity") == "BLOCKING"), None)
    blocked = (not isinstance(status, str) or status.startswith("WAIT_")
               or intake.get("status") == "BLOCKED" or blocking is not None)
    if blocked:
        reason = (blocking.get("message") if blocking else None) or result.get("reason")
        code = (blocking.get("code") if blocking else None) or status or "DATA_UNAVAILABLE"
        return _payload("DATA_ALERT", "WAIT", str(code), str(reason or code))

    mode = result.get("sourceDataMode")
    if mode == "synthetic" or status == "SYNTHETIC_TEST_ONLY":
        return _payload("STATUS", "WAIT", "SYNTHETIC_TEST_ONLY",
                        "Synthetic test input is not real market evidence")

    candidate = result.get("researchCandidate")
    eligible = (mode == "recorded"
                and result.get("researchEligible") is True
                and intake.get("researchEligible") is True
                and result.get("executable") is False
                and status == "RESEARCH_REVIEWED")
    if candidate in {"BUY", "SELL"}:
        if result.get("executable") is not False:
            return _payload("DATA_ALERT", "WAIT", "EXECUTION_GUARD_BLOCKED",
                            "Notification rejected because executable was not explicitly false")
        if not eligible:
            return _payload("DATA_ALERT", "WAIT", "SOURCE_NOT_ELIGIBLE",
                            "Unverified, synthetic, or blocked evidence cannot produce a research notification")
        return _payload("RESEARCH_SIGNAL", candidate, "RESEARCH_CANDIDATE",
                        f"{candidate} research candidate; not executable")
    if result.get("executable") is not False:
        return _payload("DATA_ALERT", "WAIT", "EXECUTION_GUARD_BLOCKED",
                        "Notification rejected because executable was not explicitly false")
    if candidate not in {None, "NONE", "WAIT", "BUY", "SELL"}:
        return _payload("DATA_ALERT", "WAIT", "INVALID_RESEARCH_CANDIDATE",
                        "Notification rejected because the candidate value is invalid")
    return _payload("RESEARCH_SIGNAL", "WAIT", "WAIT", "No eligible research candidate")


def _payload(kind: str, signal: str, code: str, message: str) -> dict:
    return {"kind": kind, "signal": signal, "code": code, "message": message,
            "researchOnly": True, "executable": False,
            "delivery": "DRY_RUN_LOCAL_PREVIEW_NO_EXTERNAL_SEND"}


class ResearchNotificationJournal:
    """Persist notification state transitions for a later, separately enabled sender."""

    def __init__(self, database: str | pathlib.Path):
        self.db = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS research_notification_state(
            id INTEGER PRIMARY KEY CHECK(id=1), state_key TEXT NOT NULL,
            payload TEXT NOT NULL, changed_utc TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS research_notification_events(
            id INTEGER PRIMARY KEY, state_key TEXT NOT NULL, transition TEXT NOT NULL,
            occurred_utc TEXT NOT NULL, payload TEXT NOT NULL
          );
        """)

    def close(self):
        self.db.close()

    def observe(self, result: dict | None, now: dt.datetime) -> dict:
        current = build_notification(result)
        state_key = f"{current['kind']}:{current['signal']}:{current['code']}"
        stamp = parse_utc(now.isoformat()).isoformat().replace("+00:00", "Z")
        events = []
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT state_key,payload FROM research_notification_state WHERE id=1"
            ).fetchone()
            if previous is None:
                events.append(self._record(state_key, "RAISED", stamp, current))
            elif previous["state_key"] != state_key:
                old_payload = json.loads(previous["payload"])
                events.append(self._record(previous["state_key"], "RECOVERED", stamp, old_payload))
                events.append(self._record(state_key, "RAISED", stamp, current))
            self.db.execute(
                "INSERT INTO research_notification_state(id,state_key,payload,changed_utc) VALUES(1,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET state_key=excluded.state_key,payload=excluded.payload,"
                "changed_utc=excluded.changed_utc", (state_key, json.dumps(current, sort_keys=True), stamp)
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return {"events": events, "current": current,
                "delivery": "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND",
                "signal": "WAIT", "executable": False}

    def history(self) -> list[dict]:
        return [json.loads(row[0]) | {"transition": row[1], "atUTC": row[2]}
                for row in self.db.execute(
                    "SELECT payload,transition,occurred_utc FROM research_notification_events ORDER BY id"
                )]

    def _record(self, state_key: str, transition: str, stamp: str, payload: dict) -> dict:
        event = {**payload, "transition": transition}
        self.db.execute(
            "INSERT INTO research_notification_events(state_key,transition,occurred_utc,payload) "
            "VALUES(?,?,?,?)", (state_key, transition, stamp,
                                 json.dumps(event, sort_keys=True, separators=(",", ":")))
        )
        return event | {"atUTC": stamp}
