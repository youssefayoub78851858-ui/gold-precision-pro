"""Offline Capital Demo replay receipts matched to the SAME bar timestamps.

This is not a provider connection, nor an independent publication, licensing,
broker-calendar or first-seen attestation. It never emits quote prices and
never authorizes paper/live orders.
"""
from __future__ import annotations

import datetime as dt

from capital_demo_offline_batch_audit import audit_disabled_history_pages
from capital_demo_receipt_preflight import inspect_receipts, ORIGIN
from capital_demo_offline_adapter import _normalize_row, RESOLUTIONS

MODE = "CAPITAL_DEMO_OFFLINE_RECEIPT_HISTORY_LINK_V1"


def _base(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False, "providerRequestsMade": 0,
        "brokerOrdersSent": 0, "sourceRightsIndependentlyVerified": False,
        "historicalPagesIndependentlyAuthenticated": False,
        "firstSeenIndependentlyAttested": False,
        "brokerSessionCalendarVerified": False,
        "historicalBidAskExecutionVerified": False,
        "independentHoldoutValidated": False,
        "matchingBarCounts": {"M15": 0, "H1": 0, "H4": 0},
        "allFrameTimestampsMatched": False,
    }


def inspect_link(packet):
    fail = _base("UNTRUSTED_OR_INCOMPLETE_OFFLINE_LINK")
    try:
        if not isinstance(packet, dict) or set(packet) != {
                "dataOrigin", "plan", "pages", "receipts"}:
            return fail
        if packet["dataOrigin"] != "SYNTHETIC_TEST_ONLY":
            return fail
        plan, pages, receipts = packet["plan"], packet["pages"], packet["receipts"]
        if not isinstance(receipts, dict) or receipts.get("dataOrigin") != ORIGIN:
            return fail
        history = audit_disabled_history_pages(plan, pages)
        if history["status"] == "BLOCKED":
            return _base("HISTORICAL_OHLC_AUDIT_BLOCKED")
        clock = inspect_receipts(receipts)
        if clock["status"] == "BLOCKED":
            return _base("RECEIPT_CHRONOLOGY_REJECTED")
        if not isinstance(plan, dict) or not isinstance(pages, dict):
            return fail

        # A planning snapshot made after a purported historical decision
        # cannot retroactively demonstrate that its bars had been received.
        # Equality is a conservative fixture consistency rule, never proof.
        if plan["asOfUTC"] != receipts["decisionUTC"]:
            return _base("HISTORY_PLAN_AFTER_OR_BEFORE_DECISION")
        expected = {}
        for frame, (_, width) in RESOLUTIONS.items():
            seen = set()
            for page in pages[frame]:
                for raw in page["response"]["prices"]:
                    stamp, _, _ = _normalize_row(
                        raw, width,
                        dt.datetime.fromisoformat(
                            plan["asOfUTC"].replace("Z", "+00:00")
                        )
                    )
                    seen.add(stamp)
            expected[frame] = seen

        # The two audits independently accepted their local shapes.
        # Only identical per-bar OPEN timestamps may be correlated.
        counts = {}
        for frame in RESOLUTIONS:
            claimed = {bar["openUTC"] for bar in receipts["frames"][frame]}
            if claimed != expected[frame]:
                return _base("RECEIPT_BARS_DIFFER_FROM_HISTORICAL_BARS")
            counts[frame] = len(claimed)
        if counts != history["receivedClosedCounts"]:
            return _base("HISTORY_RECEIPT_COUNT_CONTRADICTION")
        result = _base("NO_INDEPENDENT_RIGHTS_RECEIPTS_OR_FORWARD_RESULTS")
        result.update({
            "status": ("OFFLINE_BARS_MATCH_BUT_GAPS_UNVERIFIED"
                       if history["status"] == "INCOMPLETE_OR_UNVERIFIED"
                       or clock["status"] == "INCOMPLETE_GAPPY_OR_STALE_UNATTESTED_GEOMETRY"
                       else "OFFLINE_SYNTHETIC_BARS_TIMESTAMPS_MATCH_ONLY"),
            "matchingBarCounts": counts,
            "allFrameTimestampsMatched": True,
            "h4FullyCoveredByBoth": clock["h4FullyCoveredByBoth"],
            "unverifiedSessionGaps": clock["perFrameUnclassifiedUTCGridGaps"],
        })
        return result
    except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError):
        return fail
