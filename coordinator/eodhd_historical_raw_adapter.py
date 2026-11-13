"""Offline raw EODHD 1m REST JSON inspection; NO fetching or orders.

Only checks provider-documented timestamp (Unix seconds UTC), datetime
(YYYY-MM-DD HH:MM:SS UTC), and gmtoffset (0). Prices are quarantined: bid,
ask, midpoint and direct compatibility with FOREX WebSocket are UNKNOWN.
"""
from __future__ import annotations
import datetime as dt
from eodhd_historical_1m_intake import MAX_MINUTES, review_normalized_eodhd_history

UTC = dt.timezone.utc


def _reject(reason):
    return {
        "status": "HISTORY_QUARANTINED", "signal": "WAIT", "executable": False,
        "readyForPaper": False, "researchEligible": False,
        "mayMergeWithLiveBidAsk": False, "priceBasis": "UNVERIFIED",
        "sourceRequestsMade": 0, "secretReads": 0, "payments": 0,
        "oneMinuteCount": 0,
        "completeClosedBarCounts": {"M15": 0, "H1": 0, "H4": 0},
        "blockingReasons": [reason],
        "marketClosureClassificationVerified": False,
    }


def review_raw_eodhd_intraday_1m(raw_rows, *, as_of):
    """Input an already obtained JSON array; accept no credentials/permissions."""
    if not isinstance(raw_rows, list) or not 0 < len(raw_rows) <= MAX_MINUTES:
        return _reject("RAW_HISTORY_JSON_ARRAY_OR_SIZE_INVALID")
    normalized = []
    for row in raw_rows:
        if not isinstance(row, dict):
            return _reject("RAW_HISTORY_ROW_INVALID")
        stamp = row.get("timestamp")
        if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp <= 0:
            return _reject("RAW_HISTORY_UNIX_SECONDS_INVALID")
        if isinstance(row.get("gmtoffset"), bool) or row.get("gmtoffset") != 0:
            return _reject("RAW_HISTORY_UNVERIFIED_GMT_OFFSET")
        if not isinstance(row.get("datetime"), str):
            return _reject("RAW_HISTORY_DATETIME_INVALID")
        try:
            parsed = dt.datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S")
            if parsed.strftime("%Y-%m-%d %H:%M:%S") != row["datetime"]:
                return _reject("RAW_HISTORY_DATETIME_NONCANONICAL")
            utc = parsed.replace(tzinfo=UTC)
            if int(utc.timestamp()) != stamp:
                return _reject("RAW_HISTORY_TIMESTAMP_DATETIME_CONFLICT")
        except (ValueError, OverflowError):
            return _reject("RAW_HISTORY_DATETIME_INVALID")
        normalized.append({
            "openTime": utc.isoformat().replace("+00:00", "Z"),
            **{name: row.get(name) for name in ("open", "high", "low", "close")},
        })
    outcome = review_normalized_eodhd_history(
        {"provider": "EODHD", "symbol": "XAUUSD.FOREX",
         "interval": "1m", "candles": normalized}, as_of=as_of)
    outcome["rawSchema"] = "EODHD_INTRADAY_1M_UNIX_TIMESTAMP_GMTOFFSET_DATETIME"
    outcome["offlineRawPayloadValidated"] = outcome["oneMinuteCount"] == len(raw_rows)
    outcome["historicalConventionVerified"] = False
    outcome["providerSubscriptionUsed"] = False
    return outcome
