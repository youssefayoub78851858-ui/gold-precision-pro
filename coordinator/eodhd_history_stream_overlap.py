"""Offline historical REST / recorded WebSocket overlap diagnostics only.

Inputs are an independently obtained raw EODHD 1m JSON array and an
independently captured private EODHD WebSocket closed-candle snapshot.
A numerical match is NOT source authentication, a license, or authority to
mix historical REST OHLC with live bid/ask quotes in the research engine.
Never fetches, subscribes, reads credentials, or trades.
"""
from __future__ import annotations

import datetime as dt
from statistics import median

from eodhd_historical_raw_adapter import review_raw_eodhd_intraday_1m
from eodhd_research_bridge import _audit_bars
from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
MIN_MATCHED_M15 = 8
FIELDS = ("open", "high", "low", "close")
FAMILIES = {"BID": "bidFrames", "MID": "frames", "ASK": "askFrames"}


def _blocked(reason, **additional):
    result = {
        "status": "WAIT_HISTORY_STREAM_OVERLAP",
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "paperOrdersAllowed": False,
        "mayMergeHistoricalAndStreamBars": False,
        "historicalPriceBasisVerified": False,
        "sourceEntitlementVerifiedByDiagnostics": False,
        "independentSessionCalendarVerified": False,
        "sourceRequestsMade": 0,
        "secretReads": 0,
        "payments": 0,
        "matchedCompleteM15": 0,
        "requiredMatchedM15ForDiagnostic": MIN_MATCHED_M15,
        "blockingReasons": [reason,
                            "REST_VS_WEBSOCKET_PRICE_BASIS_AND_RIGHTS_STILL_UNVERIFIED"],
    }
    result.update(additional)
    return result


def _full_rest_m15(raw_rows):
    # The caller already validated Unix UTC timestamp, OHLC, ordering and
    # complete minutes. Partial 15m groups are NEVER filled.
    groups = {}
    for row in raw_rows:
        slot = row["timestamp"] // 60
        start = slot // 15 * 15
        groups.setdefault(start, []).append(row)
    complete = {}
    for start, rows in groups.items():
        if len(rows) != 15 or any(row["timestamp"] != (start + i) * 60
                                  for i, row in enumerate(rows)):
            continue
        complete[dt.datetime.fromtimestamp(start * 60, tz=UTC)
                 .isoformat().replace("+00:00", "Z")] = {
            "open": rows[0]["open"],
            "high": max(x["high"] for x in rows),
            "low": min(x["low"] for x in rows),
            "close": rows[-1]["close"],
        }
    return complete


def compare_eodhd_rest_to_stream(raw_rows, snapshot, *, as_of):
    """Numerical overlap only; always WAIT, even for perfectly equal OHLC."""
    try:
        clock = parse_utc(as_of.isoformat())
    except (TypeError, ValueError, AttributeError):
        return _blocked("INDEPENDENT_UTC_CLOCK_MISSING")
    history = review_raw_eodhd_intraday_1m(raw_rows, as_of=clock)
    if not history.get("offlineRawPayloadValidated"):
        return _blocked("HISTORICAL_REST_INPUT_REJECTED",
                        historyRejectCodes=history.get("blockingReasons", []))
    if (not isinstance(snapshot, dict) or
            snapshot.get("provider") != "EODHD" or
            snapshot.get("instrument") != "XAU/USD" or
            snapshot.get("quoteType") != "INDICATIVE_MIDQUOTE_OHLC" or
            snapshot.get("mode") != "REVIEW_ONLY" or
            snapshot.get("signal") != "WAIT" or
            snapshot.get("executable") is not False or
            snapshot.get("researchEligible") is not False or
            snapshot.get("readyForTrading") is not False):
        return _blocked("STREAM_SNAPSHOT_IDENTITY_OR_SAFETY_INVALID")
    try:
        counts = _audit_bars(snapshot)
    except (TypeError, ValueError, AttributeError, KeyError) as error:
        # Do not leak payload contents in an error diagnostic.
        _ = error
        return _blocked("STREAM_BID_ASK_GEOMETRY_REJECTED")
    history_m15 = _full_rest_m15(raw_rows)
    live_m15 = {r["openTime"]: r for r in snapshot["frames"]["M15"]}
    matches = sorted(set(history_m15).intersection(live_m15))
    count = len(matches)
    if count < MIN_MATCHED_M15:
        return _blocked("INSUFFICIENT_SAME_UTC_M15_OVERLAP",
                        matchedCompleteM15=count,
                        historicalCompleteM15=len(history_m15),
                        recordedClosedBarCounts=counts,
                        missingToDiagnostic=MIN_MATCHED_M15 - count)
    error_by_series = {}
    for label, family in FAMILIES.items():
        stream_rows = {r["openTime"]: r for r in snapshot[family]["M15"]}
        deltas = [
            abs(history_m15[stamp][field] - stream_rows[stamp][field])
            for stamp in matches for field in FIELDS
        ]
        # Differences are provider price units (USD per troy oz for XAUUSD);
        # no claim about latency, spreads, real-world fills, or correct basis.
        error_by_series[label] = {
            "medianAbsoluteOhlcDifference": round(median(deltas), 8),
            "maximumAbsoluteOhlcDifference": round(max(deltas), 8),
            "meanAbsoluteOhlcDifference": round(sum(deltas) / len(deltas), 8),
        }
    return _blocked(
        "NUMERICAL_OVERLAP_OBSERVED_BUT_BASIS_NOT_AUTHORIZED",
        matchedCompleteM15=count,
        historicalCompleteM15=len(history_m15),
        recordedClosedBarCounts=counts,
        missingToDiagnostic=0,
        differencesUSDPerOunce=error_by_series,
        closestObservedSeriesOnlyNotVerifiedBasis=min(
            FAMILIES, key=lambda x: error_by_series[x]["meanAbsoluteOhlcDifference"]),
        informationalComparisonOnly=True,
    )
