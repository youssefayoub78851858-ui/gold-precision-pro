"""Offline, read-only assessment of Render disk snapshot *metadata*.

Render's list-snapshots API includes short-lived snapshotKey values; those
keys are never returned, printed, persisted, or needed here. This module
does not query Render, operate on any disk, or prove archive recoverability.
A recent disk snapshot is NOT evidence that the BiQuote vault exists in it.
"""
from __future__ import annotations

import datetime as dt
import json
import re

UTC = dt.timezone.utc
MODE = "BIQUOTE_RENDER_SNAPSHOT_METADATA_GATE_NO_RESTORE_V1"
MAX_ITEMS = 100
RETENTION_DAYS = 7
RECENT_HOURS = 36
SAFE = {
    "mode": MODE,
    "status": "BLOCKED",
    "reason": "SNAPSHOT_LIST_NOT_VERIFIED",
    "snapshotMetadataRecentOnly": False,
    "listedWithinSevenDays": 0,
    "latestSnapshotAgeHours": None,
    "snapshotMayContainVault": None,
    "vaultIncludedInSnapshotVerified": False,
    "independentOffsiteBackupVerified": False,
    "isolatedRestorePassed": False,
    "reviewDeployApproved": False,
    "coordinatorRestartApproved": False,
    "snapshotRestored": False,
    "rawPricesPrinted": False,
    "snapshotKeyPrinted": False,
    "marketDataRightsVerified": False,
    "brokerOrdersSent": 0,
    "providerRequestsMade": 0,
    "signal": "WAIT",
    "executable": False,
}


def _blocked(reason):
    return {**SAFE, "reason": reason}


def _utc_date(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)",
        value,
    ):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return stamp


def assess(snapshots, *, now_utc):
    """Inspect supplied snapshot metadata only; never trust it as live proof."""
    if not isinstance(now_utc, dt.datetime) or now_utc.tzinfo is None:
        return _blocked("UTC_CLOCK_REQUIRED")
    if now_utc.utcoffset() != dt.timedelta(0):
        return _blocked("UTC_CLOCK_REQUIRED")
    if not isinstance(snapshots, list) or not 0 < len(snapshots) <= MAX_ITEMS:
        return _blocked("SNAPSHOT_LIST_MISSING_OR_UNBOUNDED")
    try:
        stamps = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                raise ValueError("INVALID_SNAPSHOT_ITEM")
            stamp = _utc_date(snapshot.get("createdAt"))
            if stamp > now_utc:
                return _blocked("FUTURE_SNAPSHOT_TIME_OR_CLOCK_SKEW")
            stamps.append(stamp)
    except (ValueError, TypeError, OverflowError):
        return _blocked("SNAPSHOT_METADATA_INVALID")
    age = now_utc - max(stamps)
    within_seven = sum(now_utc - stamp <= dt.timedelta(days=RETENTION_DAYS)
                       for stamp in stamps)
    recent = age <= dt.timedelta(hours=RECENT_HOURS)
    return {
        **SAFE,
        "status": "RECENT_SNAPSHOT_LISTED_NOT_ARCHIVE_PROOF"
                  if recent else "STALE_SNAPSHOT_METADATA_ONLY",
        "reason": "LIVE_VAULT_IN_SNAPSHOT_AND_RECOVERY_NOT_VERIFIED",
        "snapshotMetadataRecentOnly": bool(recent),
        "listedWithinSevenDays": within_seven,
        "latestSnapshotAgeHours": round(age.total_seconds() / 3600, 2),
    }


if __name__ == "__main__":
    # CLI cannot access Render or its disk; it requires an explicit
    # operator-provided JSON list on standard input, not credentials.
    import sys
    try:
        data = sys.stdin.read(65_536)
        parsed = json.loads(data)
    except (ValueError, UnicodeError):
        parsed = None
    print(json.dumps(assess(parsed, now_utc=dt.datetime.now(UTC)),
                     sort_keys=True))
