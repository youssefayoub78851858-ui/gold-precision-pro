"""Authenticated-only EODHD private status summary; no vendor I/O, prices, or trades.

The private bridge produces a separate snapshot on persistent disk. This helper
reports safe aggregate readiness in standby without approving any research feed.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import stat

UTC = dt.timezone.utc
SNAPSHOT_FILE = "eodhd-private-review.json"
MAX_SIZE = 250_000
FRESH_SECONDS = 30


def _base(status, reason):
    return {
        "source": "EODHD_XAUUSD_PRIVATE_REVIEW",
        "status": status,
        "reason": reason,
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "providerAccess": False,
        "paperRunning": False,
        "priceVisible": False,
        "countsAreNotMarketDataVerification": True,
        "sourceRequestsOnThisCall": 0,
        "closedBarCounts": {"M15": 0, "H1": 0, "H4": 0},
    }


def _utc_time(value):
    if not isinstance(value, str):
        raise ValueError("UTC timestamp string required")
    value = value.replace("Z", "+00:00") if value.endswith("Z") else value
    timestamp = dt.datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() != dt.timedelta():
        raise ValueError("UTC timestamp required")
    return timestamp.astimezone(UTC)


def read_private_status(directory, *, now=None):
    """No access tokens, raw prices, account details or vendor network calls."""
    now = dt.datetime.now(UTC) if now is None else now
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() != dt.timedelta():
        raise ValueError("Independent UTC clock required")
    path = pathlib.Path(directory) / SNAPSHOT_FILE
    try:
        st = path.lstat()
    except FileNotFoundError:
        return _base("NOT_CONNECTED", "PRIVATE_BRIDGE_NOT_STARTED")
    except OSError:
        return _base("BLOCKED", "PRIVATE_STATUS_STORAGE_UNAVAILABLE")
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SIZE or (stat.S_IMODE(st.st_mode) & 0o077):
        return _base("BLOCKED", "PRIVATE_STATUS_FILE_SECURITY_OR_SIZE_INVALID")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("provider") != "EODHD" or raw.get("instrument") != "XAU/USD":
            raise ValueError("Incorrect provider or symbol")
        if (raw.get("mode") != "REVIEW_ONLY" or raw.get("signal") != "WAIT"
                or raw.get("executable") is not False or raw.get("researchEligible") is not False
                or raw.get("readyForTrading") is not False):
            raise ValueError("Research-only contract changed")
        frames = raw.get("frames")
        if not isinstance(frames, dict) or set(frames) != {"M15", "H1", "H4"}:
            raise ValueError("Frame keys invalid")
        counts = {}
        for key in ("M15", "H1", "H4"):
            if not isinstance(frames[key], list) or len(frames[key]) > 320:
                raise ValueError("Frame count invalid")
            counts[key] = len(frames[key])
        quote = raw.get("latestQuote")
        if quote is None:
            out = _base("WAIT_NO_VERIFIED_QUOTE", "BRIDGE_HAS_NO_CURRENT_QUOTE")
            out["closedBarCounts"] = counts
            return out
        if not isinstance(quote, dict):
            raise ValueError("Malformed latest quote")
        stamp = _utc_time(quote.get("timeUTC"))
        age = (now - stamp).total_seconds()
        file_age = now.timestamp() - st.st_mtime
        if age < -5 or file_age < -5:
            return _base("BLOCKED", "FUTURE_CLOCK_OR_FILE_TIMESTAMP")
        if age > FRESH_SECONDS or file_age > FRESH_SECONDS:
            return _base("WAIT_STALE", "QUOTE_OR_STATUS_FILE_IS_STALE")
        if age < 0:
            return _base("BLOCKED", "QUOTATION_CLOCK_AHEAD_OF_HOST")
        out = _base("WAIT_REVIEW_OBSERVATION_ONLY", "LIVE_RESEARCH_PIPELINE_NOT_AUTHORIZED")
        out["closedBarCounts"] = counts
        out["lastQuoteAgeSeconds"] = int(age)
        out["lastSnapshotAgeSeconds"] = int(max(0, file_age))
        return out
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError):
        return _base("BLOCKED", "PRIVATE_STATUS_SNAPSHOT_INVALID")
