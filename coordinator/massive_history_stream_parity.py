"""Historical REST vs WebSocket synthetic-BBO comparison, no source merging.

Input snapshots must come from the local synthetic-only Massive adapters.
Identical numbers cannot prove shared vendor feed, entitlement, chronology,
independent trading calendar, real-time availability or paper admissibility.
"""
from __future__ import annotations

import math
import datetime as dt


def canonical_utc_stamp(value):
    """Same UTC instant may serialize as Z or .000Z; never coerce local clocks."""
    if not isinstance(value, str) or not value.endswith('Z'):
        return None
    try:
        instant = dt.datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError:
        return None
    return instant if instant.utcoffset() == dt.timedelta(0) else None


def compare_synthetic_history_and_stream(historical: object, streamed: object) -> dict:
    """Report only diagnostic counts and reason codes, never BBO prices."""
    valid = (isinstance(historical, dict) and isinstance(streamed, dict)
             and historical.get("mode") == "OFFLINE_SYNTHETIC_MASSIVE_BBO_REVIEW"
             and historical.get("sourceDataMode") == "SYNTHETIC_TEST_ONLY"
             and historical.get("provider") == "Massive"
             and historical.get("signal") == "WAIT"
             and historical.get("executable") is False
             and historical.get("researchEligible") is False
             and historical.get("sameFeedRealtimeParityVerified") is False
             and streamed.get("mode") == "OFFLINE_SYNTHETIC_REVIEW_ONLY"
             and streamed.get("sourceDataMode") == "SYNTHETIC_TEST_ONLY"
             and streamed.get("provider") == "Massive"
             and streamed.get("signal") == "WAIT"
             and streamed.get("executable") is False
             and streamed.get("researchEligible") is False
             and streamed.get("historicalLiveParityVerified") is False
             and streamed.get("providerRequestsMade") == 0)
    if not valid:
        raise ValueError("UNVERIFIED_OR_UNSAFE_PARITY_INPUT")

    mismatches = []
    matched = {"M15": 0, "H1": 0, "H4": 0}
    for basis, rest_key, stream_key in (
        ("BID", "bidFrames", "bidFrames"),
        ("ASK", "askFrames", "askFrames"),
        ("MID", "midFrames", "frames"),
    ):
        rest = historical.get(rest_key)
        current = streamed.get(stream_key)
        if not isinstance(rest, dict) or not isinstance(current, dict):
            mismatches.append(basis + "_FRAMES_MISSING")
            continue
        for timeframe in matched:
            old = rest.get(timeframe)
            live = current.get(timeframe)
            if not isinstance(old, list) or not isinstance(live, list):
                mismatches.append(basis + "_" + timeframe + "_NOT_ARRAY")
                continue
            if len(old) != len(live):
                mismatches.append(basis + "_" + timeframe + "_COUNT_MISMATCH")
                continue
            for i, (a, b) in enumerate(zip(old, live)):
                if (not isinstance(a, dict) or not isinstance(b, dict) or
                        canonical_utc_stamp(a.get("openTime")) is None or
                        canonical_utc_stamp(a.get("openTime")) != canonical_utc_stamp(b.get("openTime"))):
                    mismatches.append(basis + "_" + timeframe + "_UTC_MISMATCH")
                    break
                for field in ("open", "high", "low", "close"):
                    x, y = a.get(field), b.get(field)
                    if (isinstance(x, bool) or isinstance(y, bool) or
                            not isinstance(x, (int, float)) or
                            not isinstance(y, (int, float)) or
                            not math.isfinite(x) or not math.isfinite(y) or
                            not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-8)):
                        mismatches.append(basis + "_" + timeframe + "_OHLC_MISMATCH")
                        break
                if mismatches:
                    # Price comparison did not pass; no acceptance with a
                    # partially validated or missing candle.
                    break
            else:
                matched[timeframe] += len(old) if basis == "BID" else 0
    return {
        "mode": "OFFLINE_PARITY_DIAGNOSTIC_ONLY",
        "status": "OFFLINE_NUMERICAL_PARITY_ONLY" if not mismatches else "BLOCKED_SYNTHETIC_PARITY",
        "syntheticBidBarsCompared": matched,
        "mismatchCodes": sorted(set(mismatches)),
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "paperOrdersAllowed": False,
        "sameFeedProven": False,
        "historyMayMergeWithStream": False,
        "realMarketPricesValidated": False,
        "sessionCoverageVerified": False,
        "sourceLicenseVerified": False,
        "providerRequestsMade": 0,
        "tradesPlaced": 0,
        "warning": "Matching synthetic OHLC does not prove historical/live quote source parity, rights or execution quality",
    }
