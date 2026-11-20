"""Capital Demo HISTORICAL response audit: offline, sanitized, non-admitting.

This never performs HTTP, touches credentials or preserves/private-displays
quotes. It inspects only caller-provided responses against a reconstructed
disabled historical request plan; count gaps and parity conservatively.
Even a perfect result is NOT source-rights, freshness or trading evidence.
"""
import datetime as dt

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_offline_adapter import (
    RESOLUTIONS, _normalize_row, _cross_frame_bid_ask_parity,
    _direct_h1_h4_bid_ask_parity
)


def _base(status, reason):
    return {
        "mode": "CAPITAL_DEMO_OFFLINE_BATCH_RESPONSE_AUDIT_V1",
        "status": status, "reason": reason, "signal": "WAIT",
        "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "sourceRightsVerified": False, "brokerCalendarVerified": False,
        "pointInTimeReceiptsVerified": False, "forwardHoldoutValidated": False,
        "credentialsUsed": False, "networkAllowed": False,
        "providerRequestsMade": 0, "brokerOrdersSent": 0,
        "receivedClosedCounts": {"M15": 0, "H1": 0, "H4": 0},
        "unverifiedMissingUTCGridSlots": {"M15": 0, "H1": 0, "H4": 0}
    }


def audit_disabled_history_pages(plan, pages):
    """Return only safe COUNTS/flags. Never echo input, epic, token or price."""
    fail = lambda code: _base("BLOCKED", code)
    if not isinstance(plan, dict) or plan.get("status") != "INERT_PLAN_ONLY":
        return fail("MISSING_INERT_APPROVED_PLAN_SHAPE")
    try:
        # No external plan-supplied authorization flag can change the gate.
        p = plan["requests"]
        epic = p["M15"][0]["request"]["path"].removeprefix("/api/v1/prices/")
        reconstructed = plan_demo_closed_history(
            epic, plan["firstOpenUTC"], plan["endExclusiveUTC"],
            plan["asOfUTC"], bars_per_call=plan["barsPerCall"]
        )
        if reconstructed != plan:
            return fail("TAMPERED_OR_INCONSISTENT_REQUEST_PLAN")
        if not isinstance(pages, dict) or set(pages) != set(RESOLUTIONS):
            return fail("M15_H1_H4_OFFLINE_RESPONSES_REQUIRED")
        rows = {}
        received = {}
        missing = {}
        for frame, (_, width) in RESOLUTIONS.items():
            batch = pages[frame]
            planned = p[frame]
            if not isinstance(batch, list) or len(batch) != len(planned):
                return fail("BATCH_COUNT_OR_COMPLETENESS_UNVERIFIED")
            seen = set()
            by_side = {"bid": [], "ask": []}
            prior = None
            for chunk, wrapped in zip(planned, batch):
                if not isinstance(wrapped, dict) or set(wrapped) != {"httpStatus", "response"}:
                    return fail("UNTRUSTED_HTTP_WRAPPER")
                if type(wrapped["httpStatus"]) is not int or wrapped["httpStatus"] != 200:
                    return fail("HTTP_NOT_VERIFIED_SUCCESS")
                reply = wrapped["response"]
                if not isinstance(reply, dict) or "prices" not in reply:
                    return fail("MALFORMED_PROVIDER_RESPONSE")
                expected_resolution = chunk["request"]["query"]["resolution"]
                if reply.get("resolution", expected_resolution) != expected_resolution:
                    return fail("BROKER_RESOLUTION_MISMATCH")
                if reply.get("epic", epic) != epic:
                    return fail("BROKER_EPIC_MISMATCH")
                prices = reply["prices"]
                if not isinstance(prices, list) or len(prices) > 1000:
                    return fail("INVALID_BOUNDED_PROVIDER_PAGE")
                start = chunk["firstExpectedOpenUTC"]
                end = chunk["expectedEndExclusiveUTC"]
                for raw in prices:
                    stamp, bid, ask = _normalize_row(
                        raw, width, dt.datetime.fromisoformat(
                            plan["asOfUTC"].replace("Z", "+00:00")
                        )
                    )
                    if stamp < start or stamp >= end:
                        return fail("OUT_OF_EXPECTED_CANDLE_WINDOW")
                    if stamp in seen or (prior is not None and stamp <= prior):
                        return fail("DUPLICATE_OR_REORDERED_BROKER_HISTORY")
                    seen.add(stamp)
                    prior = stamp
                    by_side["bid"].append(bid)
                    by_side["ask"].append(ask)
            rows[frame] = by_side
            received[frame] = len(seen)
            missing[frame] = plan["expectedClosedBarCounts"][frame] - len(seen)
            if missing[frame] < 0:
                return fail("RECEIVED_MORE_THAN_PLANNED_CLOSED_SLOTS")
        parity = _cross_frame_bid_ask_parity(rows)
        direct = _direct_h1_h4_bid_ask_parity(rows)
        any_mismatch = any(z["fullyCoveredDisagreed"] for z in [*parity.values(), direct])
        any_incomplete = any(z["notFullyCovered"] for z in [*parity.values(), direct])
        gaps = any(missing.values())
        result = _base("INCOMPLETE_OR_UNVERIFIED",
                       "NO_INDEPENDENT_BROKER_SESSION_OR_POINT_IN_TIME_ATTESTATION")
        result.update({
            "receivedClosedCounts": received,
            "unverifiedMissingUTCGridSlots": missing,
            "crossFrameParityCounts": parity,
            "directH4FromH1ParityCounts": direct,
            "bidAskShapeAccepted": True,
            "fullUtcGridCoverage": not gaps,
            "localCrossFrameParityFullyCovered": not (any_mismatch or any_incomplete),
            "observedPriceConflict": any_mismatch,
            "potentialUnexplainedMissingHistory": gaps or any_incomplete
        })
        if any_mismatch:
            result["status"] = "BLOCKED"
            result["reason"] = "BID_ASK_CROSS_FRAME_OHLC_CONFLICT"
        elif gaps or any_incomplete:
            result["reason"] = "MISSING_UTC_SLOTS_OR_CROSS_FRAME_CONSTITUENTS_UNVERIFIED"
        else:
            result["status"] = "LOCAL_GEOMETRY_ONLY_NOT_ADMITTED"
            result["reason"] = "NO_INDEPENDENT_BROKER_RIGHTS_RECEIPTS_COSTS_OR_FORWARD_HOLDOUT"
        return result
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, AttributeError):
        return fail("UNTRUSTED_OR_INVALID_OFFLINE_BATCH_DATA")
