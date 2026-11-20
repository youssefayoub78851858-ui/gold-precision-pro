"""Offline Capital.com Demo Gold history batch planner — NO API access.

Capital's documented prices endpoint accepts from/to, resolution and max<=1000.
A to-boundary may be inclusive: the future reader MUST reject unexpected
extra/out-of-range timestamps, duplicate conflicts, and insufficient coverage.
This module ONLY builds disabled GET descriptions. It never fetches, stores
market prices, parses secrets, creates a session, or authorizes research/trades.
"""
from __future__ import annotations
import datetime as dt

from capital_demo_offline_adapter import (
    RESOLUTIONS, _as_of_utc, _valid_epic,
    audit_demo_get_only_request, demo_price_get_blueprint
)

MAX_WINDOW_DAYS = 120
MAX_ROWS_PER_CALL = 900   # Below provider max 1000, leaves overlap headroom.
MAX_BATCHES_PER_FRAME = 128
UTC = dt.timezone.utc


def _stamp(x):
    return x.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _blocked(code):
    return {
        "mode": "CAPITAL_DEMO_INERT_HISTORICAL_BATCH_PLAN_V1",
        "status": "BLOCKED", "reason": code, "signal": "WAIT",
        "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "credentialsUsed": False, "providerRequestsMade": 0,
        "brokerOrdersSent": 0, "sourceRightsVerified": False,
        "kycRequiredNow": False, "connected": False,
        "requests": {}, "expectedClosedBarCounts": {}
    }


def plan_demo_closed_history(epic, start_utc, end_utc, as_of_utc, *, bars_per_call=MAX_ROWS_PER_CALL):
    """Plan exact UTC-grid slots across three frames, no authority to run.

    end_utc is EXCLUSIVE of the last candle OPEN. The corresponding last
    candle must have CLOSED by as_of_utc. Each request's 'to' may include
    an additional opening slot, so response validation must use our stated
    [start, end) window, never blindly trust endpoint max or boundaries.
    """
    try:
        if not _valid_epic(epic):
            raise ValueError("UNVERIFIED_GOLD_EPIC")
        if type(bars_per_call) is not int or not 2 <= bars_per_call <= MAX_ROWS_PER_CALL:
            raise ValueError("INVALID_INERT_CHUNK_SIZE")
        start = _as_of_utc(start_utc)
        end = _as_of_utc(end_utc)
        asof = _as_of_utc(as_of_utc)
        if not (dt.datetime(2020, 1, 1, tzinfo=UTC) <= start < end <= asof):
            raise ValueError("NONCLOSED_OR_INVERTED_RANGE")
        if end-start > dt.timedelta(days=MAX_WINDOW_DAYS):
            raise ValueError("EXCESSIVE_HISTORY_WINDOW")
        # H4 alignment also ensures M15 and H1 alignment, all UTC.
        if any(int(t.timestamp()) % 14400 for t in (start, end)):
            raise ValueError("H4_GRID_BOUNDARIES_REQUIRED")

        plans = {}
        counts = {}
        total = 0
        for frame, (_, width) in RESOLUTIONS.items():
            n = int((end-start).total_seconds()) // width
            if n < 1 or n > 12000:
                raise ValueError("FRAME_BAR_COUNT_NOT_BOUNDED")
            chunks = []
            current = start
            remaining = n
            while remaining:
                take = min(remaining, bars_per_call)
                stop = current + dt.timedelta(seconds=take*width)
                spec = demo_price_get_blueprint(epic, frame, current, stop)
                inspected = audit_demo_get_only_request(spec)
                if inspected["requestShapeAcceptable"] is not True or inspected["networkAllowed"] is not False:
                    raise ValueError("UNSAFE_REQUEST_BLUEPRINT")
                chunks.append({
                    "request": spec,
                    "firstExpectedOpenUTC": _stamp(current),
                    "expectedEndExclusiveUTC": _stamp(stop),
                    "expectedClosedSlots": take,
                    "providerToBoundMayBeInclusive": True,
                    "responseWindowMustBeVerified": True
                })
                remaining -= take
                current = stop
                if len(chunks) > MAX_BATCHES_PER_FRAME:
                    raise ValueError("EXCESSIVE_BATCH_COUNT")
            if current != end or sum(x["expectedClosedSlots"] for x in chunks) != n:
                raise ValueError("HISTORY_PARTITION_MISMATCH")
            plans[frame] = chunks
            counts[frame] = n
            total += len(chunks)
        return {
            **_blocked("NO_TRADING_OR_DATA_RIGHTS_AUTHORIZATION"),
            "status": "INERT_PLAN_ONLY",
            "asOfUTC": _stamp(asof), "firstOpenUTC": _stamp(start),
            "endExclusiveUTC": _stamp(end),
            "requestCount": total, "requests": plans,
            "expectedClosedBarCounts": counts,
            "lastUserAction": "DEFER_KYC_UNTIL_APPROVED_FINAL_CONNECTION",
            "liveAccountHostAllowed": False,
            "orderRouteAllowed": False,
            "autoExecute": False
        }
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        reason = str(exc)
        # Never echo arbitrary user text, keys, URLs or market data into logs.
        known = {
            "UNVERIFIED_GOLD_EPIC", "INVALID_INERT_CHUNK_SIZE",
            "NONCLOSED_OR_INVERTED_RANGE", "EXCESSIVE_HISTORY_WINDOW",
            "H4_GRID_BOUNDARIES_REQUIRED", "FRAME_BAR_COUNT_NOT_BOUNDED",
            "UNSAFE_REQUEST_BLUEPRINT", "EXCESSIVE_BATCH_COUNT",
            "HISTORY_PARTITION_MISMATCH", "AS_OF_EXPLICIT_UTC_REQUIRED"
        }
        return _blocked(reason if reason in known else "INVALID_REQUEST_OR_UTC")
