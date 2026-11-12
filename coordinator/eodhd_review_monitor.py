"""Offline private EODHD -> existing monitoring and notification journals.

Only audits a private snapshot. No network, vendor authentication, analysis
engine, paper account, trading or notification delivery. Never returns quotes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import stat

from eodhd_private_readiness import MAX_SIZE, SNAPSHOT_FILE, read_private_status
from eodhd_research_bridge import review_eodhd_snapshot
from research_monitor import ResearchAlertMonitor
from research_notification import ResearchNotificationJournal
from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
ALLOWED_REASON = re.compile(r"[A-Z0-9_]{3,90}\Z")
STATUS_CODES = {
    "NOT_CONNECTED": "EODHD_PRIVATE_BRIDGE_NOT_CONNECTED",
    "BLOCKED": "EODHD_PRIVATE_SNAPSHOT_SECURITY_OR_FORMAT_BLOCKED",
    "WAIT_STALE": "EODHD_PRIVATE_QUOTE_OR_SNAPSHOT_STALE",
    "WAIT_NO_VERIFIED_QUOTE": "EODHD_PRIVATE_QUOTE_MISSING",
}


def _read_private_snapshot(directory, now):
    """Independent no-follow, permission, size and clock check before JSON read.

    This is an additional check after the existing safe readiness check; status
    remains WAIT even if the producer changes the file during the two reads.
    """
    path = pathlib.Path(directory) / SNAPSHOT_FILE
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or (stat.S_IMODE(info.st_mode) & 0o077)
                or info.st_size > MAX_SIZE or info.st_size <= 0
                or now.timestamp() - info.st_mtime > 30 or info.st_mtime > now.timestamp() + 5):
            raise ValueError("EODHD_PRIVATE_FILE_NOT_SAFE_OR_FRESH")
        data = os.read(fd, MAX_SIZE + 1)
        if len(data) > MAX_SIZE:
            raise ValueError("EODHD_PRIVATE_FILE_TOO_LARGE")
        parsed = json.loads(data.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("EODHD_PRIVATE_JSON_NOT_OBJECT")
        return parsed
    finally:
        os.close(fd)


def poll_private_review(directory, as_of: dt.datetime) -> dict:
    """Produce a non-voting, non-executable observation for existing journals."""
    now = parse_utc(as_of.isoformat())
    readiness = read_private_status(directory, now=now)
    data_status = readiness["status"]
    codes = []
    if data_status != "WAIT_REVIEW_OBSERVATION_ONLY":
        codes = [STATUS_CODES.get(data_status, "EODHD_PRIVATE_STATE_UNKNOWN")]
    else:
        try:
            snapshot = _read_private_snapshot(directory, now)
            # Do NOT pass a SourcePolicy, IndependentEvidence or engine approval.
            # The staging bridge must refuse the research engine by design.
            staged = review_eodhd_snapshot(snapshot, now)
            if (staged.get("signal") != "WAIT" or staged.get("executable") is not False
                    or staged.get("researchEligible") is not False
                    or staged.get("engineStatus") != "NOT_INVOKED"
                    or staged.get("providerConnectionStarted") is not False):
                raise ValueError("EODHD_STAGING_CONTRACT_INVALID")
            for item in staged.get("blockingReasons", []):
                code = item if isinstance(item, str) and ALLOWED_REASON.fullmatch(item) else "EODHD_PRIVATE_REVIEW_REJECTED"
                if code not in codes:
                    codes.append(code)
            if not codes:
                codes.append("EODHD_PRIVATE_REVIEW_EVIDENCE_NOT_VERIFIED")
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            codes = ["EODHD_PRIVATE_SNAPSHOT_READ_REJECTED"]
    return {
        "status": "WAIT_EODHD_INTAKE",
        "sourceDataMode": "eodhd_private_unverified",
        "provider": "EODHD", "dataStatus": data_status,
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "researchCandidate": "NONE", "engineStatus": "NOT_INVOKED",
        "paperRunning": False, "providerAccessStartedByMonitor": False,
        "sourceRequestsMade": 0, "notificationsSent": 0,
        "closedBarCounts": readiness.get("closedBarCounts", {"M15": 0, "H1": 0, "H4": 0}),
        "intake": {"status": "BLOCKED", "blockingReasons": codes},
        "reason": codes[0],
    }


def observe_once(directory, alert_db, notification_db, as_of: dt.datetime) -> dict:
    """Persist deduplicated local alert and notification transitions for one poll."""
    now = parse_utc(as_of.isoformat())
    result = poll_private_review(directory, now)
    alerts = ResearchAlertMonitor(alert_db)
    try:
        alert_result = alerts.observe(result, now)
    finally:
        alerts.close()
    journal = ResearchNotificationJournal(notification_db)
    try:
        notification_result = journal.observe(result, now)
    finally:
        journal.close()
    return {
        "mode": "PRIVATE_REVIEW_MONITOR_ONLY",
        "observedUTC": now.isoformat().replace("+00:00", "Z"),
        "result": result, "alerts": alert_result, "notifications": notification_result,
        "signal": "WAIT", "executable": False,
        "marketDataAccess": False, "paperRunning": False,
    }


def main():
    parser = argparse.ArgumentParser(description="One offline EODHD private-review monitor poll")
    parser.add_argument("--snapshot-directory", required=True)
    parser.add_argument("--alert-db", required=True)
    parser.add_argument("--notification-db", required=True)
    args = parser.parse_args()
    now = dt.datetime.now(UTC)
    print(json.dumps(observe_once(args.snapshot_directory, args.alert_db,
                                  args.notification_db, now), sort_keys=True))


if __name__ == "__main__":
    main()
