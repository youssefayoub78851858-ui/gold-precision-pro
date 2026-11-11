"""Decision-only policy for an external Research Only process watchdog.

This module never starts, stops, or restarts a process. A host supervisor may
consume the result and restart the research service after a failed health check.
"""
from __future__ import annotations

import datetime as dt

from xauusd_feed_gate import parse_utc, retry_delay_seconds


def assess_watchdog(*, process_alive: bool, paper_only: bool,
                    heartbeat_utc: str | None, now: dt.datetime,
                    stale_after_seconds: int = 120, failure_count: int = 0,
                    retry_base_seconds: int = 5,
                    retry_max_seconds: int = 300) -> dict:
    """Return HEALTHY or RESTART_REQUIRED from injected process/heartbeat state."""
    if isinstance(stale_after_seconds, bool) or not isinstance(stale_after_seconds, int) or stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be a positive integer")
    retry_delay = retry_delay_seconds(failure_count, retry_base_seconds, retry_max_seconds)
    current = parse_utc(now.isoformat())
    reason = None
    age = None
    if process_alive is not True:
        reason = "PROCESS_NOT_ALIVE"
    elif paper_only is not True:
        reason = "PAPER_ONLY_GUARD_MISSING"
    elif not isinstance(heartbeat_utc, str):
        reason = "HEARTBEAT_MISSING"
    else:
        try:
            heartbeat = parse_utc(heartbeat_utc)
            age = (current - heartbeat).total_seconds()
            if age < 0:
                reason = "HEARTBEAT_FROM_FUTURE"
            elif age > stale_after_seconds:
                reason = "HEARTBEAT_STALE"
        except (TypeError, ValueError):
            reason = "HEARTBEAT_INVALID"

    if reason is None:
        return {"status": "HEALTHY", "action": "NONE", "reason": None,
                "heartbeatAgeSeconds": age, "signal": "WAIT", "executable": False}
    return {"status": "UNHEALTHY", "action": "RESTART_REQUIRED", "reason": reason,
            "heartbeatAgeSeconds": age,
            "retryDelaySeconds": retry_delay,
            "signal": "WAIT", "executable": False}
