"""Local, response-only alert state for Research Only pipeline observations.

This monitor records alert transitions in SQLite so repeated polls and process
restarts do not emit duplicate notifications. It has no network or messaging
transport; consumers receive local audit events only.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3

from xauusd_feed_gate import parse_utc


def _alert(code: str, source: str, message: str) -> dict:
    return {"code": code, "source": source, "message": message}


def _alerts_for(result: dict | None) -> dict[str, dict]:
    alerts = {}

    def add(item):
        if not isinstance(item, dict):
            return
        code, source = item.get("code"), item.get("source", "system")
        if not isinstance(code, str) or not code:
            return
        key = f"{code}:{source}"
        alerts[key] = _alert(code, str(source), str(item.get("message", code)))

    if result is None:
        add(_alert("PIPELINE_UNAVAILABLE", "xauusd", "No pipeline observation was received"))
        return alerts
    if not isinstance(result, dict):
        add(_alert("MONITOR_RESULT_INVALID", "xauusd", "Pipeline observation has an invalid shape"))
        return alerts

    status = result.get("status")
    if status == "WAIT_ENGINE_FAILURE":
        add(_alert("ENGINE_UNAVAILABLE", "research", result.get("reason", "Research engine failed")))
    elif status == "WAIT_CONTEXT_MISSING":
        add(_alert("EVIDENCE_UNAVAILABLE", "research", result.get("reason", "Research evidence is missing")))
    elif status == "WAIT_SOURCE_NOT_ELIGIBLE":
        add(_alert("SOURCE_UNVERIFIED", "xauusd", result.get("reason", "Source rights are not verified")))

    intake = result.get("intake") or {}
    for reason in intake.get("blockingReasons", []):
        if not isinstance(reason, str) or reason == "SYNTHETIC_DATA_NOT_REAL_MARKET_EVIDENCE":
            continue
        prefix = reason.split(":", 1)[0]
        source = prefix.removesuffix("_REJECTED").lower()
        lower = reason.lower()
        if "forming" in lower or "unclosed" in lower:
            code = "CANDLE_UNCLOSED"
        elif "stale" in lower or "future" in lower:
            code = "DATA_STALE_OR_FUTURE"
        elif "gap" in lower or "missing" in lower or "schedule" in lower:
            code = "DATA_GAP_OR_MISSING"
        else:
            code = "INTAKE_BLOCKED"
        add(_alert(code, source, reason))

    diagnostic_alerts = (result.get("diagnostics") or {}).get("alerts") or {}
    for item in diagnostic_alerts.get("items", []):
        if isinstance(item, dict) and item.get("severity") == "BLOCKING":
            add(item)

    return alerts


class ResearchAlertMonitor:
    """Persist alert state and return only new alert/recovery transitions."""

    def __init__(self, database: str | pathlib.Path):
        self.db = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS research_alert_state(
            alert_key TEXT PRIMARY KEY, code TEXT NOT NULL, source TEXT NOT NULL,
            message TEXT NOT NULL, active INTEGER NOT NULL, changed_utc TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS research_alert_events(
            id INTEGER PRIMARY KEY, alert_key TEXT NOT NULL, transition TEXT NOT NULL,
            occurred_utc TEXT NOT NULL, payload TEXT NOT NULL
          );
        """)

    def close(self):
        self.db.close()

    def observe(self, result: dict | None, now: dt.datetime) -> dict:
        stamp = parse_utc(now.isoformat()).isoformat().replace("+00:00", "Z")
        current = _alerts_for(result)
        events = []
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous_rows = self.db.execute(
                "SELECT * FROM research_alert_state WHERE active=1"
            ).fetchall()
            previous = {row["alert_key"]: row for row in previous_rows}

            for key, item in current.items():
                old = previous.get(key)
                transition = "RAISED" if old is None else None
                if old is not None:
                    self.db.execute(
                        "UPDATE research_alert_state SET message=?, changed_utc=? WHERE alert_key=?",
                        (item["message"], stamp, key),
                    )
                else:
                    inactive = self.db.execute(
                        "SELECT active FROM research_alert_state WHERE alert_key=?", (key,)
                    ).fetchone()
                    transition = "RAISED" if inactive is None else "REOPENED"
                    self.db.execute(
                        "INSERT INTO research_alert_state VALUES(?,?,?,?,1,?) "
                        "ON CONFLICT(alert_key) DO UPDATE SET code=excluded.code,source=excluded.source,"
                        "message=excluded.message,active=1,changed_utc=excluded.changed_utc",
                        (key, item["code"], item["source"], item["message"], stamp),
                    )
                if transition:
                    events.append(self._record(key, transition, stamp, item))

            for key, old in previous.items():
                if key in current:
                    continue
                item = {"code": old["code"], "source": old["source"],
                        "message": old["message"]}
                self.db.execute(
                    "UPDATE research_alert_state SET active=0,changed_utc=? WHERE alert_key=?",
                    (stamp, key),
                )
                events.append(self._record(key, "RECOVERED", stamp, item))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

        return {"events": events, "activeAlerts": list(current.values()),
                "delivery": "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND",
                "signal": "WAIT", "executable": False}

    def _record(self, key, transition, stamp, item):
        payload = {**item, "transition": transition}
        self.db.execute(
            "INSERT INTO research_alert_events(alert_key,transition,occurred_utc,payload) VALUES(?,?,?,?)",
            (key, transition, stamp, json.dumps(payload, sort_keys=True, separators=(",", ":"))),
        )
        return {**payload, "atUTC": stamp}

    def history(self) -> list[dict]:
        return [json.loads(row[0]) | {"atUTC": row[1]}
                for row in self.db.execute(
                    "SELECT payload,occurred_utc FROM research_alert_events ORDER BY id"
                )]
