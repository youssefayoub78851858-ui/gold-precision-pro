"""Read-only BiQuote cross-timeframe evidence: diagnostic, NEVER a trade gate.

No transport, provider keys or disk storage. This only distinguishes
retention-window overlap, missing M15 constituents, and OHLC disagreement.
A no-tick hour may be a real session break, but *without an independently
verified broker calendar*, cannot be labeled a valid market closure.
"""
from __future__ import annotations

import datetime as dt
from biquote_offline_source_audit import FRAMES, _frame, _utc, _close
from biquote_session_gap_audit import reference_window_for_missing_slot

UTC = dt.timezone.utc
FIELDS = ("open", "high", "low", "close")


def diagnose_biquote_overlap(frame_envelopes, *, now):
    report = {
        "status": "UNVERIFIED_DIAGNOSTIC_ONLY",
        "signal": "WAIT", "executable": False, "researchEligible": False,
        "sourceRequestsMade": 0, "orderRequestsMade": 0,
        "sessionCalendarIndependentlyVerified": False,
        "historicalBidAskQuoteParityProven": False,
        "frames": {}, "overlap": {}, "error": None
    }
    if (not isinstance(now, dt.datetime) or now.tzinfo is None
            or now.utcoffset() != dt.timedelta(0)):
        report["error"] = "INDEPENDENT_UTC_REQUIRED"
        return report
    if not isinstance(frame_envelopes, dict) or set(frame_envelopes) != set(FRAMES):
        report["error"] = "THREE_FRAMES_REQUIRED"
        return report
    verified = {}
    try:
        for frame, (interval, seconds) in FRAMES.items():
            envelope = frame_envelopes[frame]
            verified[frame] = _frame(envelope, interval, seconds, now)
            opens = sorted(verified[frame])
            missing_slots = sum(
                max(0, (later - earlier) // seconds - 1)
                for earlier, later in zip(opens, opens[1:])
            )
            report["frames"][frame] = {
                "closedCount": len(opens),
                "oldestClosedUTC": (
                    dt.datetime.fromtimestamp(opens[0], UTC).isoformat().replace("+00:00", "Z")
                    if opens else None),
                "newestClosedUTC": (
                    dt.datetime.fromtimestamp(opens[-1], UTC).isoformat().replace("+00:00", "Z")
                    if opens else None),
                "nonConsecutivePairs": sum(
                    later - earlier != seconds for earlier, later in zip(opens, opens[1:])),
                "missingSlotsUnclassifiedByCalendar": missing_slots,
            }
    except (ValueError, TypeError, OverflowError) as exc:
        report["error"] = str(exc)
        return report

    m15 = verified["M15"]
    if not m15:
        report["error"] = "NO_CLOSED_M15"
        return report
    low, high = min(m15), max(m15)
    for tf, width in (("H1", 3600), ("H4", 14400)):
        count = width // 900
        stats = {
            "higherClosedBars": len(verified[tf]),
            "outsideM15Retention": 0,
            "oldestOrNewestWindowEdgeIncomplete": 0,
            "fullyCoveredCompared": 0,
            "fullyCoveredAgree": 0,
            "fullyCoveredOHLCDisagree": 0,
            "internalM15ConstituentGaps": 0,
            # Partial groups still allow a strict NECESSARY (not sufficient)
            # OHLC-bound check. Never fill missing slots or certify parity.
            "partialGroupsWithObservedM15": 0,
            "partialObservedOHLCBoundDisagreements": 0,
            "partialObservedOHLCFields": {field: 0 for field in FIELDS},
            "partialMissingM15ReferencePauseCandidates": 0,
            "partialMissingM15OutsideReferenceTradingTime": 0,
            "partialMissingM15UnknownSeason": 0,
            "examplesOfInternalGapUTC": [],
            "examplesOfOHLCMismatchUTC": [],
            "disagreedOHLCFields": {field: 0 for field in FIELDS}
        }
        for start, actual in sorted(verified[tf].items()):
            end = start + (count - 1) * 900
            if start > high or end < low:
                stats["outsideM15Retention"] += 1
                continue
            if start < low or end > high:
                stats["oldestOrNewestWindowEdgeIncomplete"] += 1
                continue
            members = [m15.get(start + i*900) for i in range(count)]
            if any(member is None for member in members):
                stats["internalM15ConstituentGaps"] += 1
                missing = [start + i*900 for i,member in enumerate(members)
                           if member is None]
                # This is a VENDOR-DECLARED SESSION REFERENCE only, never
                # evidence from the upstream MetaTrader broker calendar.
                for missing_start in missing:
                    hint=reference_window_for_missing_slot(
                        dt.datetime.fromtimestamp(missing_start, UTC),900)
                    if hint is True:
                        stats["partialMissingM15ReferencePauseCandidates"] += 1
                    elif hint is False:
                        stats["partialMissingM15OutsideReferenceTradingTime"] += 1
                    else:
                        stats["partialMissingM15UnknownSeason"] += 1
                observed=[b for b in members if b is not None]
                if observed:
                    stats["partialGroupsWithObservedM15"] += 1
                    # Observed M15 high/low MUST fit within H1/H4 high/low.
                    # This detects impossible subsets even when the complete
                    # H4 aggregate cannot be reconstructed.
                    bad=[]
                    if actual["high"] < max(b["high"] for b in observed) and not _close(
                            actual["high"],max(b["high"] for b in observed)):
                        bad.append("high")
                    if actual["low"] > min(b["low"] for b in observed) and not _close(
                            actual["low"],min(b["low"] for b in observed)):
                        bad.append("low")
                    # Only check open or close when their exact 15-minute
                    # constituents are present. Never infer missing prices.
                    if members[0] is not None and not _close(
                            actual["open"],members[0]["open"]):
                        bad.append("open")
                    if members[-1] is not None and not _close(
                            actual["close"],members[-1]["close"]):
                        bad.append("close")
                    if bad:
                        stats["partialObservedOHLCBoundDisagreements"] += 1
                        for field in bad:
                            stats["partialObservedOHLCFields"][field] += 1
                if len(stats["examplesOfInternalGapUTC"]) < 4:
                    stats["examplesOfInternalGapUTC"].append({
                        "higherOpenUTC": dt.datetime.fromtimestamp(
                            start, UTC).isoformat().replace("+00:00", "Z"),
                        "missingM15UTC": [
                            dt.datetime.fromtimestamp(t, UTC).isoformat().replace("+00:00", "Z")
                            for t in missing[:5]],
                        "numberMissing": len(missing)
                    })
                continue
            stats["fullyCoveredCompared"] += 1
            expected = {
                "open": members[0]["open"], "high": max(x["high"] for x in members),
                "low": min(x["low"] for x in members),
                "close": members[-1]["close"]
            }
            bad_keys = [key for key in FIELDS if not _close(actual[key], expected[key])]
            if bad_keys:
                stats["fullyCoveredOHLCDisagree"] += 1
                for key in bad_keys:
                    stats["disagreedOHLCFields"][key] += 1
                if len(stats["examplesOfOHLCMismatchUTC"]) < 4:
                    stats["examplesOfOHLCMismatchUTC"].append({
                        "higherOpenUTC": dt.datetime.fromtimestamp(
                            start, UTC).isoformat().replace("+00:00", "Z"),
                        "fields": bad_keys
                    })
            else:
                stats["fullyCoveredAgree"] += 1
        report["overlap"][tf] = stats
    return report
