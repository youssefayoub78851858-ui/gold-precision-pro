"""Quarantined, offline XAUUSD.FOREX 1-minute history audit.

Input is a NORMALIZED external candidate (not raw EODHD REST response):
  {"provider":"EODHD", "symbol":"XAUUSD.FOREX", "interval":"1m",
   "candles":[{"openTime":"2026-11-02T00:00:00Z",
                "open":4000.0,"high":4001.0,"low":3999.0,"close":4000.5}]}

Do not infer that historical OHLC values represent bid, ask or midpoint.
Do not concatenate this candidate with live WebSocket bid/ask M15 candles.
UTC timestamps, official sessions, licenses and streaming parity require
independent external evidence, never flags supplied by candidate data.
No networking, credentials, provider calls or market/execution orders.
"""
from __future__ import annotations

import datetime as dt
import math

from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
WIDTHS = {"M15": 15, "H1": 60, "H4": 240}
MAX_MINUTES = 50_000
BAR_FIELDS = ("open", "high", "low", "close")
MINIMUM = {"M15": 50, "H1": 50, "H4": 50}


def _fail(reason: str) -> dict:
    return {
        "status": "HISTORY_QUARANTINED", "signal": "WAIT", "executable": False,
        "readyForPaper": False, "researchEligible": False,
        "mayMergeWithLiveBidAsk": False, "priceBasis": "UNVERIFIED",
        "sourceRequestsMade": 0, "secretReads": 0, "payments": 0,
        "oneMinuteCount": 0,
        "completeClosedBarCounts": {key: 0 for key in WIDTHS},
        "blockingReasons": [reason],
        "marketClosureClassificationVerified": False,
    }


def _epoch_minute(time_value, as_of):
    parsed = parse_utc(time_value)
    if parsed.second or parsed.microsecond:
        raise ValueError("HISTORY_1M_TIME_NOT_MINUTE_ALIGNED")
    second = int(parsed.timestamp())
    if second % 60:
        raise ValueError("HISTORY_1M_TIME_NOT_MINUTE_ALIGNED")
    if parsed + dt.timedelta(minutes=1) > as_of:
        raise ValueError("HISTORY_UNCLOSED_OR_FUTURE_MINUTE")
    return second // 60


def _prices(candle):
    if not isinstance(candle, dict):
        raise ValueError("HISTORY_INVALID_CANDLE")
    values = []
    for name in BAR_FIELDS:
        value = candle.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("HISTORY_INVALID_OHLC_TYPE")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("HISTORY_INVALID_OHLC_VALUE")
        values.append(value)
    opened, high, low, closed = values
    if low > min(opened, high, closed) or high < max(opened, low, closed):
        raise ValueError("HISTORY_INVALID_OHLC_RANGE")


def review_normalized_eodhd_history(document, *, as_of):
    """Compute complete closed bar groups; quarantine regardless of row counts.

    Reject timestamps without explicit UTC. Gaps may be weekend/holiday or
    unavailable data, never auto-fill, silently classify or bridge them.
    Input-provided entitlement/basis/parity fields grant no authority.
    """
    try:
        now = parse_utc(as_of.isoformat())
    except (TypeError, ValueError, AttributeError):
        return _fail("INDEPENDENT_UTC_CLOCK_REQUIRED")
    if not isinstance(document, dict):
        return _fail("HISTORY_DOCUMENT_INVALID")
    if (document.get("provider") != "EODHD"
            or document.get("symbol") != "XAUUSD.FOREX"
            or document.get("interval") != "1m"):
        return _fail("HISTORY_SOURCE_IDENTITY_MISMATCH")
    minutes = document.get("candles")
    if not isinstance(minutes, list) or not 0 < len(minutes) <= MAX_MINUTES:
        return _fail("HISTORY_SIZE_OR_CANDLES_INVALID")

    # This set only certifies geometry within a normalized offline sample;
    # there is no authentication or real-provider provenance here.
    slots = []
    previous = None
    discontinuities = 0
    missing_minutes = 0
    try:
        for candle in minutes:
            if not isinstance(candle, dict):
                raise ValueError("HISTORY_INVALID_CANDLE")
            slot = _epoch_minute(candle.get("openTime"), now)
            if previous is not None:
                if slot <= previous:
                    raise ValueError("HISTORY_1M_DUPLICATE_OR_NONMONOTONIC")
                if slot > previous + 1:
                    discontinuities += 1
                    missing_minutes += slot - previous - 1
            _prices(candle)
            slots.append(slot)
            previous = slot
    except (TypeError, ValueError, OverflowError) as error:
        code = str(error)
        if code not in {
            "HISTORY_1M_TIME_NOT_MINUTE_ALIGNED",
            "HISTORY_UNCLOSED_OR_FUTURE_MINUTE",
            "HISTORY_INVALID_CANDLE",
            "HISTORY_INVALID_OHLC_TYPE",
            "HISTORY_INVALID_OHLC_VALUE",
            "HISTORY_INVALID_OHLC_RANGE",
            "HISTORY_1M_DUPLICATE_OR_NONMONOTONIC",
        }:
            code = "HISTORY_1M_UTC_INVALID"
        return _fail(code)

    # Count a higher-timeframe bar only if every one-minute slot is present.
    # Anchoring by UTC epoch-minute avoids accidental partial H4 aggregation.
    counts = {}
    for tf, width in WIDTHS.items():
        full_groups = 0
        candidate_group = None
        count = 0
        first = None
        last = None
        for slot in slots:
            group = slot // width
            if group != candidate_group:
                if count == width and first == candidate_group * width and last == (candidate_group + 1) * width - 1:
                    full_groups += 1
                candidate_group = group
                first = slot
                count = 0
            count += 1
            last = slot
        if count == width and first == candidate_group * width and last == (candidate_group + 1) * width - 1:
            full_groups += 1
        counts[tf] = full_groups

    gaps = {tf: max(0, MINIMUM[tf] - counts[tf]) for tf in WIDTHS}
    blockers = [
        "HISTORICAL_PRICE_BASIS_AND_STREAM_BID_ASK_PARITY_UNVERIFIED",
        "INDEPENDENT_SESSION_CALENDAR_AND_PROVENANCE_UNVERIFIED",
        "PROVIDER_ENTITLEMENT_FOR_ACTUAL_API_CALL_NOT_ACTIVATED",
        "LIVE_RESEARCH_AND_PAPER_NOT_APPROVED",
    ]
    if any(gaps.values()):
        blockers.insert(0, "COMPLETE_HISTORICAL_WARMUP_INSUFFICIENT")
    if discontinuities:
        blockers.append("UNCLASSIFIED_HISTORICAL_TIME_GAPS")
    return {
        "status": "HISTORY_QUARANTINED", "signal": "WAIT", "executable": False,
        "readyForPaper": False, "researchEligible": False,
        "mayMergeWithLiveBidAsk": False,
        "priceBasis": "UNVERIFIED", "sourceRequestsMade": 0,
        "secretReads": 0, "payments": 0,
        "oneMinuteCount": len(slots),
        "completeClosedBarCounts": counts,
        "missingCompleteBarsToMinimum": gaps,
        "numberOfUnclassifiedDiscontinuities": discontinuities,
        "missingOneMinuteSlotsWithoutCalendar": missing_minutes,
        "firstUTCMinute": minutes[0]["openTime"],
        "lastUTCMinute": minutes[-1]["openTime"],
        "marketClosureClassificationVerified": False,
        "blockingReasons": blockers,
        "note": "Count geometry cannot prove source, license, BID/ASK parity, or trading validity",
    }
