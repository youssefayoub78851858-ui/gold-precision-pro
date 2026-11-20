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


def _same(a, b):
    return abs(a-b) <= max(0.00001, abs(b)*1e-8)


def _price_parity(whole, members):
    if not members:
        return False
    return all(
        _same(whole[name], expected)
        for name, expected in {
            "open": members[0]["open"],
            "high": max(x["high"] for x in members),
            "low": min(x["low"] for x in members),
            "close": members[-1]["close"]
        }.items()
    )


def _cross_frame_bid_ask_parity(rows):
    """Offline source geometry only; missing lower bars cannot count as matches.

    Check both BID and ASK independently against the exact 4/16 M15
    components. Never compare unrelated time ranges or fill broker breaks.
    """
    maps = {
        side: {row["openTime"]: row for row in rows["M15"][side]}
        for side in ("bid", "ask")
    }
    report = {}
    for frame, quarters in (("H1", 4), ("H4", 16)):
        counts = {"fullyCoveredMatched": 0, "fullyCoveredDisagreed": 0,
                  "notFullyCovered": 0}
        for bid_whole, ask_whole in zip(rows[frame]["bid"], rows[frame]["ask"]):
            opened = dt.datetime.fromisoformat(
                bid_whole["openTime"].replace("Z", "+00:00")
            )
            stamps = [
                (opened + dt.timedelta(minutes=15*i)).isoformat().replace("+00:00", "Z")
                for i in range(quarters)
            ]
            bid_parts = [maps["bid"].get(t) for t in stamps]
            ask_parts = [maps["ask"].get(t) for t in stamps]
            if any(x is None for x in bid_parts + ask_parts):
                counts["notFullyCovered"] += 1
            elif (_price_parity(bid_whole, bid_parts) and
                  _price_parity(ask_whole, ask_parts)):
                counts["fullyCoveredMatched"] += 1
            else:
                counts["fullyCoveredDisagreed"] += 1
        report[frame] = counts
    return report


def _direct_h1_h4_bid_ask_parity(rows):
    """Compare the independent H1 and H4 provider frames, even if M15 is absent.

    An H4 needs exactly four aligned, closed H1 members for BOTH BID and
    ASK. Gaps are not fabricated and no license/trading claim is possible.
    """
    hourly = {
        side: {row["openTime"]: row for row in rows["H1"][side]}
        for side in ("bid", "ask")
    }
    counts = {"fullyCoveredMatched": 0, "fullyCoveredDisagreed": 0,
              "notFullyCovered": 0}
    for bid_whole, ask_whole in zip(rows["H4"]["bid"], rows["H4"]["ask"]):
        opened = dt.datetime.fromisoformat(
            bid_whole["openTime"].replace("Z", "+00:00")
        )
        stamps = [
            (opened + dt.timedelta(hours=i)).isoformat().replace("+00:00", "Z")
            for i in range(4)
        ]
        bid_parts = [hourly["bid"].get(t) for t in stamps]
        ask_parts = [hourly["ask"].get(t) for t in stamps]
        if any(x is None for x in bid_parts + ask_parts):
            counts["notFullyCovered"] += 1
        elif (_price_parity(bid_whole, bid_parts) and
              _price_parity(ask_whole, ask_parts)):
            counts["fullyCoveredMatched"] += 1
        else:
            counts["fullyCoveredDisagreed"] += 1
    return counts


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
    result["crossFrameBidAskParity"] = _cross_frame_bid_ask_parity(rows)
    result["h4FromH1BidAskParity"] = _direct_h1_h4_bid_ask_parity(rows)
    result["fullCrossFrameCoverageVerified"] = all(
        data["notFullyCovered"] == 0 and data["fullyCoveredDisagreed"] == 0
        for data in list(result["crossFrameBidAskParity"].values()) +
                    [result["h4FromH1BidAskParity"]]
    )
    result["stagedBidFrames"] = {tf: rows[tf]["bid"] for tf in RESOLUTIONS}
    result["stagedAskFrames"] = {tf: rows[tf]["ask"] for tf in RESOLUTIONS}
    result["blockingReasons"] = [
        "PRIVATE_RENDER_DATA_RIGHTS_UNCONFIRMED",
        "API_CREDENTIALS_AND_BROKER_GOLD_EPIC_UNVERIFIED",
        "INDEPENDENT_BROKER_SESSION_AND_SNAPSHOT_CLOCK_MISSING",
        "HISTORICAL_BID_ASK_PARITY_NOT_PROVEN_WITH_LIVE_DEMO",
        "NO_RESEARCH_OR_TRADING_ADMISSION"
    ]
    if any(x["fullyCoveredDisagreed"] for x in result["crossFrameBidAskParity"].values()):
        result["blockingReasons"].append("H1_H4_M15_BID_ASK_AGGREGATION_MISMATCH")
    if any(x["notFullyCovered"] for x in result["crossFrameBidAskParity"].values()):
        result["blockingReasons"].append("H1_H4_M15_BID_ASK_COVERAGE_INCOMPLETE")
    if result["h4FromH1BidAskParity"]["fullyCoveredDisagreed"]:
        result["blockingReasons"].append("H4_H1_DIRECT_BID_ASK_AGGREGATION_MISMATCH")
    if result["h4FromH1BidAskParity"]["notFullyCovered"]:
        result["blockingReasons"].append("H4_H1_DIRECT_BID_ASK_COVERAGE_INCOMPLETE")
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


def audit_demo_get_only_request(blueprint):
    """Offline deny-by-default boundary for a FUTURE Capital Demo history reader.

    Validates only an INERT history-request specification. Does not connect,
    authenticate, log secrets, grant source rights or authorize order calls.
    This deliberately rejects all POST methods, /session, live domains,
    redirects encoded as URLs, unknown query params and enabled requests.
    """
    result = {
        "mode": "CAPITAL_DEMO_GET_ONLY_INERT_REQUEST_SHAPE_AUDIT",
        "status": "BLOCKED", "reason": "INVALID_OR_UNTRUSTED_REQUEST",
        "requestShapeAcceptable": False,
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "dataRightsVerified": False, "tradeEligible": False,
        "paperTradingAllowed": False, "providerRequestsMade": 0,
        "httpRequestsMade": 0, "credentialsUsed": False,
        "networkAllowed": False, "orderEndpointsSupported": False,
        "liveEndpointSupported": False
    }
    if not isinstance(blueprint, dict) or set(blueprint) != {
        "method", "baseUrl", "path", "query", "enabled",
        "requiresExplicitCloudRights", "providerRequestsMade", "containsCredentials"
    }:
        return result
    if (blueprint["method"] != "GET" or blueprint["baseUrl"] != DEMO_BASE_URL or
            blueprint["enabled"] is not False or
            blueprint["requiresExplicitCloudRights"] is not True or
            blueprint["providerRequestsMade"] != 0 or
            isinstance(blueprint["providerRequestsMade"], bool) or
            blueprint["containsCredentials"] is not False):
        return result
    path = blueprint["path"]
    prefix = "/api/v1/prices/"
    if not isinstance(path, str) or not path.startswith(prefix) or not _valid_epic(path[len(prefix):]):
        return result
    query = blueprint["query"]
    if not isinstance(query, dict) or set(query) != {"resolution", "from", "to", "max"}:
        return result
    if (query["resolution"] not in {frame[0] for frame in RESOLUTIONS.values()} or
            query["max"] != 1000 or isinstance(query["max"], bool)):
        return result
    try:
        values = []
        for name in ("from", "to"):
            value = query[name]
            if not isinstance(value, str) or not re.fullmatch(
                r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", value
            ):
                return result
            parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            if parsed.strftime("%Y-%m-%dT%H:%M:%S") != value:
                return result
            values.append(parsed)
        if values[0] >= values[1]:
            return result
    except (TypeError, ValueError):
        return result
    result.update({
        "status": "DEMO_HISTORICAL_GET_SHAPE_ONLY_NOT_AUTHORIZED",
        "reason": "CLOUD_DATA_RIGHTS_AND_TRADING_ENABLED_KEY_NOT_APPROVED",
        "requestShapeAcceptable": True
    })
    return result
