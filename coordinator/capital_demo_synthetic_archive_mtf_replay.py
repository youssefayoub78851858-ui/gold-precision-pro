"""Offline restart replay for sealed SYNTHETIC Capital Demo BID/ASK pages.

The real Capital.com API is NEVER contacted and this module never creates
trading credentials or accesses a real provider account. Every stored page
must have originated from the fictional TEST.GOLD.EPIC rehearsal writer.
Outputs are only sanitized geometry/counts and are never trading evidence.
"""
from __future__ import annotations

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_offline_batch_audit import audit_disabled_history_pages
from capital_demo_offline_adapter import RESOLUTIONS
from capital_demo_private_page_store import _directory, _path, _read_existing, _page

MODE = "CAPITAL_DEMO_SYNTHETIC_SEALED_MTF_RESTART_REPLAY_V1"
MAX_TOTAL_REHEARSAL_ROWS = 6000
MAX_TOTAL_REHEARSAL_CHUNKS = 48


def _blocked(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "validatedLocalPageCounts": {"M15": 0, "H1": 0, "H4": 0},
        "receivedClosedCounts": {"M15": 0, "H1": 0, "H4": 0},
        "unverifiedMissingUTCGridSlots": {"M15": 0, "H1": 0, "H4": 0},
        "locallyMatchedBidAskH1H4": False,
        "sealedLocalRehearsalPagesVerified": False,
        "marketRightsVerified": False, "genuineProviderDataVerified": False,
        "actualSessionCalendarVerified": False, "firstSeenExternallyAttested": False,
        "independentOffsiteBackupVerified": False,
        "paperTradingAuthorized": False, "realTradingAuthorized": False,
        "providerRequestsMade": 0, "ordersSent": 0,
        "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False,
    }


def _synthetic_response(chunk, source_dir):
    request = chunk["request"]
    payload_id = {
        "epic": "TEST.GOLD.EPIC",
        "resolution": request["query"]["resolution"],
        "startUTC": chunk["firstExpectedOpenUTC"],
        "endExclusiveUTC": chunk["expectedEndExclusiveUTC"],
    }
    stored = _read_existing(_path(source_dir, payload_id))
    rows = stored["rows"]
    normalized_raw = []
    for item in rows:
        row = {"snapshotTimeUTC": item["openUTC"]}
        for provider, field in (
                ("openPrice", "open"), ("highPrice", "high"),
                ("lowPrice", "low"), ("closePrice", "close")):
            row[provider] = {
                side: item[side][field] for side in ("bid", "ask")
            }
        normalized_raw.append(row)
    response = {
        "epic": "TEST.GOLD.EPIC",
        "resolution": request["query"]["resolution"],
        "prices": normalized_raw,
    }
    # This revalidates all closed UTC candles, spread/cross-side rules,
    # original first synthetic test receipt and immutable page identity.
    regenerated = _page(
        chunk, response, stored["firstLocalTestReceiptUTC"]
    )
    if regenerated != stored:
        raise ValueError("STORED_SYNTHETIC_PAGE_SEMANTICS_CHANGED")
    return {"httpStatus": 200, "response": response}


def replay_saved_synthetic_mtf(plan, dirname):
    """Fail-closed full-file restart rehearsal; never expose saved prices."""
    if not isinstance(plan, dict) or plan.get("status") != "INERT_PLAN_ONLY":
        return _blocked("DISABLED_BOUNDED_HISTORY_PLAN_REQUIRED")
    try:
        requests = plan["requests"]
        if not isinstance(requests, dict) or set(requests) != set(RESOLUTIONS):
            return _blocked("ALL_THREE_TIMEFRAMES_REQUIRED")
        if (plan["requestCount"] > MAX_TOTAL_REHEARSAL_CHUNKS or
                sum(plan["expectedClosedBarCounts"].values()) > MAX_TOTAL_REHEARSAL_ROWS):
            return _blocked("REHEARSAL_TOO_LARGE")
        identity = requests["M15"][0]["request"]["path"]
        if identity != "/api/v1/prices/TEST.GOLD.EPIC":
            return _blocked("REAL_OR_UNVERIFIED_EPIC_REJECTED")
        expected = plan_demo_closed_history(
            "TEST.GOLD.EPIC", plan["firstOpenUTC"], plan["endExclusiveUTC"],
            plan["asOfUTC"], bars_per_call=plan["barsPerCall"]
        )
        if expected != plan:
            return _blocked("UNTRUSTED_OR_CHANGED_HISTORY_PLAN")
        d = _directory(dirname)
        pages = {
            frame: [_synthetic_response(chunk, d) for chunk in requests[frame]]
            for frame in RESOLUTIONS
        }
        # Independent existing offline batch audit checks M15/H1/H4 BID and
        # ASK geometry, duplicate timestamps, time windows and parity.
        result = audit_disabled_history_pages(plan, pages)
        if result["status"] == "BLOCKED":
            return _blocked("CLOSED_BID_ASK_MTF_PARITY_OR_PAGES_REJECTED")
        count = result["receivedClosedCounts"]
        incomplete = result["status"] == "INCOMPLETE_OR_UNVERIFIED"
        accepted = _blocked(
            "MISSING_UNVERIFIED_SESSIONS_OR_CROSS_FRAME_CONSTITUENTS"
            if incomplete else "SYNTHETIC_LOCAL_PARITY_ONLY_NO_BROKER_RIGHTS"
        )
        accepted.update({
            "status": (
                "INCOMPLETE_SYNTHETIC_LOCAL_REPLAY_ONLY"
                if incomplete else "SYNTHETIC_LOCAL_MTF_PARITY_VERIFIED_ONLY"
            ),
            "validatedLocalPageCounts": {
                frame: len(pages[frame]) for frame in RESOLUTIONS
            },
            "receivedClosedCounts": dict(count),
            "unverifiedMissingUTCGridSlots": dict(
                result["unverifiedMissingUTCGridSlots"]
            ),
            "locallyMatchedBidAskH1H4": (
                result.get("localCrossFrameParityFullyCovered") is True
            ),
            "sealedLocalRehearsalPagesVerified": True,
        })
        return accepted
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError,
            OverflowError):
        return _blocked("UNTRUSTED_OR_MISSING_SYNTHETIC_PRIVATE_ARCHIVE")
