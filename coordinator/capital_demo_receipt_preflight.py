"""Capital.com Demo sanitized CLOSED-frame first-receipt audit (offline).

No provider connection, raw quotes, credentials, broker or paper orders.
Input timestamps are UNATTESTED caller assertions. A plausible chronology
or 50 H4 assembled observations cannot prove original-broker rights, a
real captured first-seen receipt, a broker calendar, or profitable signals.
"""
from __future__ import annotations

import datetime as dt
import re

UTC = dt.timezone.utc
ORIGIN = "UNATTESTED_SANITIZED_CAPITAL_DEMO_RECEIPTS"
WIDTH = {"M15": 900, "H1": 3600, "H4": 14400}
LIMIT = {"M15": 12000, "H1": 3000, "H4": 750}
CLOCK = re.compile(r"20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z")


def _stamp(value):
    if not isinstance(value, str) or CLOCK.fullmatch(value) is None:
        raise ValueError("EXPLICIT_UTC_CLOCK_REQUIRED")
    try:
        result = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("INVALID_UTC_CLOCK") from error
    if result.utcoffset() != dt.timedelta(0):
        raise ValueError("INVALID_UTC_CLOCK")
    return result


def _safe(reason):
    return {
        "mode": "CAPITAL_DEMO_SANITIZED_RECEIPT_PREFLIGHT_V1",
        "providerCandidate": "CAPITAL_COM_DEMO_SELECTED_UNCONNECTED",
        "status": "BLOCKED", "reason": reason,
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False, "connected": False,
        "sourceRightsIndependentlyVerified": False,
        "brokerSessionCalendarVerified": False,
        "firstSeenIndependentlyAttested": False,
        "realBidAskVerified": False,
        "brokerExecutionCostsVerified": False,
        "independentForwardPerformanceProven": False,
        "providerRequestsMade": 0, "brokerOrdersSent": 0,
        "receivedClosedCounts": {"M15": 0, "H1": 0, "H4": 0},
        "h4FullyCoveredByM15": 0,
        "h4FullyCoveredByH1": 0,
        "h4FullyCoveredByBoth": 0,
        "minimum21H4ConstituentGeometry": False,
        "minimum50H4ConstituentGeometry": False,
        "perFrameUnclassifiedUTCGridGaps": {"M15": 0, "H1": 0, "H4": 0},
        "latestClosedFrameAgeSeconds": {"M15": None, "H1": None, "H4": None},
    }


def inspect_receipts(packet):
    """Reject future/lookahead bars and count exact cross-frame membership.

    Non-trading and non-voting by construction. It never repeats received
    timestamps or market prices to a public caller.
    """
    fail = _safe("INVALID_UNATTESTED_CAPITAL_DEMO_RECEIPT_PACKET")
    try:
        if not isinstance(packet, dict) or set(packet) != {
                "dataOrigin", "decisionUTC", "asOfUTC", "frames"}:
            return fail
        if packet["dataOrigin"] != ORIGIN:
            return fail
        decision, as_of = _stamp(packet["decisionUTC"]), _stamp(packet["asOfUTC"])
        if decision > as_of:
            return _safe("AUDIT_ASOF_BEFORE_DECISION")
        frames = packet["frames"]
        if not isinstance(frames, dict) or set(frames) != set(WIDTH):
            return fail
        series = {}
        ages = {}
        gaps = {}
        for frame, width in WIDTH.items():
            bars = frames[frame]
            if not isinstance(bars, list) or not 1 <= len(bars) <= LIMIT[frame]:
                return fail
            rows = {}
            previous = None
            gap_count = 0
            for candle in bars:
                if not isinstance(candle, dict) or set(candle) != {
                        "openUTC", "firstSeenUTC"}:
                    return fail
                opened = _stamp(candle["openUTC"])
                received = _stamp(candle["firstSeenUTC"])
                if opened.microsecond or int(opened.timestamp()) % width:
                    return _safe("NON_GRID_ALIGNED_CLOSED_CANDLE")
                close = opened + dt.timedelta(seconds=width)
                if not (close <= received <= decision):
                    return _safe("UNCLOSED_OR_NOT_KNOWN_AT_DECISION")
                if previous is not None:
                    if opened <= previous:
                        return _safe("DUPLICATED_OR_REORDERED_CLOSED_CANDLES")
                    if (opened - previous).total_seconds() != width:
                        # Not assumed a valid weekend/holiday. Broker-specific
                        # calendar remains an independent external requirement.
                        gap_count += 1
                previous = opened
                rows[opened] = received
            series[frame] = rows
            ages[frame] = int((decision - (previous + dt.timedelta(seconds=width)))
                              .total_seconds())
            gaps[frame] = gap_count

        full_m15 = full_h1 = full_both = 0
        for h4open in series["H4"]:
            has_m15 = all(
                h4open + dt.timedelta(minutes=15 * i) in series["M15"]
                for i in range(16)
            )
            has_h1 = all(
                h4open + dt.timedelta(hours=i) in series["H1"]
                for i in range(4)
            )
            full_m15 += has_m15
            full_h1 += has_h1
            full_both += has_m15 and has_h1

        counts = {tf: len(series[tf]) for tf in WIDTH}
        # A latest M15 bar no older than 5 minutes is diagnostic only.
        # H1/H4 timeouts allow an incomplete current bar but not an
        # entire additional bar's worth of staleness.
        recent = ages["M15"] <= 300 and ages["H1"] <= 4500 and ages["H4"] <= 15300
        latest = max(series["H4"])
        latest_complete = all(
            latest + dt.timedelta(minutes=15 * i) in series["M15"]
            for i in range(16)
        ) and all(
            latest + dt.timedelta(hours=i) in series["H1"] for i in range(4)
        )
        result = _safe("UNATTESTED_TIME_AND_CONSTITUENT_GEOMETRY_ONLY")
        result.update({
            "receivedClosedCounts": counts,
            "h4FullyCoveredByM15": full_m15,
            "h4FullyCoveredByH1": full_h1,
            "h4FullyCoveredByBoth": full_both,
            "latestH4HasBothConstituentFrames": latest_complete,
            "perFrameUnclassifiedUTCGridGaps": gaps,
            "latestClosedFrameAgeSeconds": ages,
            "recentClosedFramesAtDecision": recent,
            # Counts are necessary but not sufficient: no cross-frame
            # bid/ask OHLC parity, broker sessions or actual receipt proof.
            "minimum21H4ConstituentGeometry": full_both >= 21,
            "minimum50H4ConstituentGeometry": full_both >= 50,
            "status": ("UNATTESTED_GEOMETRY_ONLY_NOT_ADMITTED"
                       if latest_complete and recent and all(v == 0 for v in gaps.values())
                       else "INCOMPLETE_GAPPY_OR_STALE_UNATTESTED_GEOMETRY"),
        })
        return result
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        return fail
