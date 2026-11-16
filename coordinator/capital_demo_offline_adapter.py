"""Capital.com Demo historical BID/ASK OFFLINE parser.

No HTTP, broker session, credential, market-data storage, orders or trading
imports. This module cannot authorize a research feed or execution.
Capital price rows: snapshotTimeUTC (often no Z); openPrice/highPrice/
lowPrice/closePrice objects with bid/ask. UTC convention and Gold epic still
require real independent evidence before future integration.
"""
from __future__ import annotations

import datetime as dt
import math
import re

from xauusd_feed_gate import parse_utc

DEMO_BASE_URL = "https://demo-api-capital.backend-capital.com"
RESOLUTIONS = {"M15": ("MINUTE_15", 900), "H1": ("HOUR", 3600), "H4": ("HOUR_4", 14400)}
OHLC = {"open": "openPrice", "high": "highPrice", "low": "lowPrice", "close": "closePrice"}
MAX_PAGES, MAX_PAGE_BARS, MAX_FRAME_BARS = 128, 1000, 12000
UTC = dt.timezone.utc


def _as_of_utc(value):
    if isinstance(value, dt.datetime) and value.tzinfo is not None and value.utcoffset() == dt.timedelta(0):
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            return parse_utc(value)
        except (TypeError, ValueError):
            pass
    raise ValueError("AS_OF_EXPLICIT_UTC_REQUIRED")


def _snapshot_utc(value):
    # Only this documented UTC field may omit an explicit Z. The display
    # snapshotTime field has no standing as an independent UTC source.
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)?", value
    ):
        raise ValueError("SNAPSHOT_UTC_INVALID")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("SNAPSHOT_UTC_INVALID") from None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("BID_ASK_PRICE_INVALID")
    return float(value)


def _normalize_row(row, seconds, as_of):
    if not isinstance(row, dict):
        raise ValueError("PRICE_ROW_INVALID")
    if "snapshotTimeUTC" not in row:
        raise ValueError("SNAPSHOT_UTC_MISSING")
    opened = _snapshot_utc(row["snapshotTimeUTC"])
    if opened.microsecond or int(opened.timestamp()) % seconds:
        raise ValueError("CANDLE_UTC_UNALIGNED")
    if opened + dt.timedelta(seconds=seconds) > as_of:
        raise ValueError("CANDLE_UNCLOSED_OR_FUTURE")
    bid, ask = {}, {}
    for key, source_key in OHLC.items():
        obj = row.get(source_key)
        if not isinstance(obj, dict):
            raise ValueError("BID_ASK_PRICE_MISSING")
        bid[key] = _price(obj.get("bid"))
        ask[key] = _price(obj.get("ask"))
        if bid[key] > ask[key]:
            # Known Capital historical aggregate issue: never silently
            # accept incorrect spread or substitute BID as evidence of ASK.
            raise ValueError("BID_ASK_CROSSED_NO_AUTO_REPAIR")
    for side in (bid, ask):
        if (side["high"] < max(side["open"], side["low"], side["close"])
                or side["low"] > min(side["open"], side["high"], side["close"])):
            raise ValueError("BID_ASK_OHLC_INVALID")
    when = opened.isoformat().replace("+00:00", "Z")
    return when, {"openTime": when, **bid}, {"openTime": when, **ask}


def _normalize_frame(pages, frame, as_of, expected_epic):
    if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError("HISTORY_PAGES_MISSING_OR_EXCESSIVE")
    resolution, seconds = RESOLUTIONS[frame]
    combined = {}
    duplicates = 0
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("HISTORY_RESPONSE_INVALID")
        if "epic" in page and page["epic"] != expected_epic:
            raise ValueError("EPIC_RESPONSE_MISMATCH")
        if "resolution" in page and page["resolution"] != resolution:
            raise ValueError("RESOLUTION_RESPONSE_MISMATCH")
        prices = page.get("prices")
        if not isinstance(prices, list) or len(prices) > MAX_PAGE_BARS:
            raise ValueError("PRICE_PAGE_INVALID_OR_OVER_LIMIT")
        for original in prices:
            when, bid, ask = _normalize_row(original, seconds, as_of)
            if when in combined:
                if combined[when] != (bid, ask):
                    raise ValueError("DUPLICATE_TIMESTAMP_CONFLICT")
                duplicates += 1
            else:
                combined[when] = (bid, ask)
        if len(combined) > MAX_FRAME_BARS:
            raise ValueError("FRAME_HISTORY_EXCESSIVE")
    if not combined:
        raise ValueError("HISTORY_EMPTY")
    keys = sorted(combined)
    dates = [dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for t in keys]
    gaps = sum((next_time - previous).total_seconds() != seconds
               for previous, next_time in zip(dates, dates[1:]))
    return {
        "bid": [combined[t][0] for t in keys],
        "ask": [combined[t][1] for t in keys],
        "count": len(keys),
        "unverifiedSessionGaps": gaps,
        "duplicatePageBoundaryRows": duplicates
    }


def _valid_epic(value):
    # Never assume a guessed symbol is the official Capital Gold epic.
    return (isinstance(value, str) and ".." not in value
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}", value) is not None)


def review_capital_demo_pages(responses_by_frame, epic, as_of_utc):
    """Validate already-supplied OFFLINE page dictionaries, always WAIT.

    No caller-supplied rights flag may override this hard disabled boundary.
    Actual prices cannot be imported here until a separately reviewed path
    satisfies contract, clock, session and provider terms.
    """
    result = {
        "provider": "CAPITAL_COM_DEMO",
        "status": "WAIT_CAPITAL_DEMO",
        "mode": "OFFLINE_STANDBY_NO_CONNECTION",
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "researchCandidate": "NONE",
        "paperTradingAllowed": False,
        "providerRequestsMade": 0, "providerConnectionStarted": False,
        "credentialsUsed": False, "liveEndpointSupported": False,
        "orderEndpointsSupported": False, "dataRightsVerified": False,
        "blockingReasons": [], "closedBarCounts": {tf: 0 for tf in RESOLUTIONS}
    }
    try:
        as_of = _as_of_utc(as_of_utc)
        if not _valid_epic(epic):
            raise ValueError("BROKER_EPIC_UNVERIFIED")
        if not isinstance(responses_by_frame, dict) or set(responses_by_frame) != set(RESOLUTIONS):
            raise ValueError("M15_H1_H4_REQUIRED")
        rows = {
            tf: _normalize_frame(responses_by_frame[tf], tf, as_of, epic)
            for tf in RESOLUTIONS
        }
    except (ValueError, TypeError, OverflowError) as exc:
        result["blockingReasons"] = [str(exc)]
        return result

    counts = {tf: rows[tf]["count"] for tf in RESOLUTIONS}
    result["offlineQuoteShapeValid"] = True
    result["closedBarCounts"] = counts
    result["minimumWarmupMissing"] = {tf: max(0, 50-counts[tf]) for tf in RESOLUTIONS}
    result["unverifiedSessionGapCounts"] = {
        tf: rows[tf]["unverifiedSessionGaps"] for tf in RESOLUTIONS
    }
    result["duplicatePageBoundaryRows"] = {
        tf: rows[tf]["duplicatePageBoundaryRows"] for tf in RESOLUTIONS
    }
    result["stagedBidFrames"] = {tf: rows[tf]["bid"] for tf in RESOLUTIONS}
    result["stagedAskFrames"] = {tf: rows[tf]["ask"] for tf in RESOLUTIONS}
    result["blockingReasons"] = [
        "PRIVATE_RENDER_DATA_RIGHTS_UNCONFIRMED",
        "API_CREDENTIALS_AND_BROKER_GOLD_EPIC_UNVERIFIED",
        "INDEPENDENT_BROKER_SESSION_AND_SNAPSHOT_CLOCK_MISSING",
        "HISTORICAL_BID_ASK_PARITY_NOT_PROVEN_WITH_LIVE_DEMO",
        "NO_RESEARCH_OR_TRADING_ADMISSION"
    ]
    if any(result["minimumWarmupMissing"].values()):
        result["blockingReasons"].append("50_CLOSED_BARS_PER_FRAME_NOT_PROVEN")
    return result


def demo_price_get_blueprint(epic, frame, start_utc, end_utc):
    """Inert only: returns Demo-specific GET request metadata, never executes."""
    if not _valid_epic(epic):
        raise ValueError("BROKER_EPIC_UNVERIFIED")
    if frame not in RESOLUTIONS:
        raise ValueError("UNSUPPORTED_RESOLUTION")
    start, end = _as_of_utc(start_utc), _as_of_utc(end_utc)
    if not start < end:
        raise ValueError("INVALID_HISTORY_RANGE")
    return {
        "method": "GET", "baseUrl": DEMO_BASE_URL,
        "path": "/api/v1/prices/" + epic,
        "query": {"resolution": RESOLUTIONS[frame][0],
                  "from": start.strftime("%Y-%m-%dT%H:%M:%S"),
                  "to": end.strftime("%Y-%m-%dT%H:%M:%S"), "max": 1000},
        "enabled": False, "requiresExplicitCloudRights": True,
        "providerRequestsMade": 0, "containsCredentials": False
    }
