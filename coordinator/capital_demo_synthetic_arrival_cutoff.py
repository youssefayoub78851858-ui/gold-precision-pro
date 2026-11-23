"""Synthetic-only decision-time cutoff for sealed Capital Demo MTF pages.

A historical page downloaded later MUST NOT be treated as data known when
a past strategy decision was made. This conservative offline rehearsal
checks whether all three sealed synthetic pages existed locally by an
explicit decision cutoff. It never infers per-candle first-seen events or
independent time attestation from a historical retrieval.
"""
from __future__ import annotations

import datetime as dt
import re

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_offline_adapter import RESOLUTIONS
from capital_demo_private_page_store import _directory, _path, _read_existing
from capital_demo_synthetic_archive_mtf_replay import replay_saved_synthetic_mtf

MODE = "CAPITAL_DEMO_SYNTHETIC_PAGE_ARRIVAL_CUTOFF_V1"
UTC_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
MAX_PAGES = 48
MAX_BARS = 6000


def _closed(reason):
    return {
        "mode": MODE,
        "status": "BLOCKED",
        "reason": reason,
        "syntheticPagesAtOrBeforeDecision": False,
        "historicalPagesAvailableBySyntheticCutoff": False,
        "closedBidAskMtfLocalParity": False,
        "totalSealedPagesChecked": 0,
        "sourceRightsVerified": False,
        "genuineBrokerFeedVerified": False,
        "independentlyAttestedFirstSeen": False,
        "historicalBackfillIsProspectiveEvidence": False,
        "independentOffsiteBackupVerified": False,
        "forwardPaperResultsVerified": False,
        "realDataReady": False,
        "providerRequestsMade": 0, "ordersSent": 0,
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False,
    }


def _utc(value):
    if not isinstance(value, str) or not UTC_PATTERN.fullmatch(value):
        raise ValueError("DECISION_Z_UTC_REQUIRED")
    instant = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    if instant.utcoffset() != dt.timedelta(0):
        raise ValueError("DECISION_Z_UTC_REQUIRED")
    return instant


def inspect_synthetic_arrival(plan, private_dir, decision_utc):
    """Never query a provider or produce a trade/admissible research input."""
    out = _closed("SYNTHETIC_ONLY_NO_INDEPENDENT_FIRST_SEEN_ATTESTATION")
    try:
        decision = _utc(decision_utc)
        if not isinstance(plan, dict) or plan.get("status") != "INERT_PLAN_ONLY":
            return _closed("INERT_ORIGINAL_BOUNDED_PLAN_REQUIRED")
        # The original plan cannot be made at a later instant and then
        # retrospectively represent a decision before that instant.
        if plan.get("asOfUTC") != decision_utc:
            return _closed("PLAN_ASOF_DECISION_MISMATCH")
        reqs = plan.get("requests")
        if not isinstance(reqs, dict) or set(reqs) != set(RESOLUTIONS):
            return _closed("CLOSED_THREE_FRAME_PLAN_REQUIRED")
        n_pages = sum(len(reqs[frame]) for frame in RESOLUTIONS)
        if (n_pages > MAX_PAGES or n_pages < 3 or
                sum(plan["expectedClosedBarCounts"].values()) > MAX_BARS):
            return _closed("UNBOUNDED_REHEARSAL_DENIED")
        for frame in RESOLUTIONS:
            if not reqs[frame] or any(
                    row["request"]["path"] != "/api/v1/prices/TEST.GOLD.EPIC"
                    for row in reqs[frame]):
                return _closed("REAL_OR_UNTRUSTED_INSTRUMENT_DENIED")
        # The separately verified replay reconstructs the complete plan,
        # validates signed pages and checks both BID and ASK cross-frame
        # aggregates. Incomplete/missing bars stay blocked for this step.
        geometry = replay_saved_synthetic_mtf(plan, private_dir)
        if (geometry["status"] != "SYNTHETIC_LOCAL_MTF_PARITY_VERIFIED_ONLY"
                or not geometry["locallyMatchedBidAskH1H4"]):
            return _closed("SEALED_MTF_REPLAY_NOT_FULLY_CONSISTENT")
        d = _directory(private_dir)
        checked = 0
        for frame in RESOLUTIONS:
            for chunk in reqs[frame]:
                key = {
                    "epic": "TEST.GOLD.EPIC",
                    "resolution": chunk["request"]["query"]["resolution"],
                    "startUTC": chunk["firstExpectedOpenUTC"],
                    "endExclusiveUTC": chunk["expectedEndExclusiveUTC"],
                }
                payload = _read_existing(_path(d, key))
                page_received = _utc(payload["firstLocalTestReceiptUTC"])
                page_closed = _utc(chunk["expectedEndExclusiveUTC"])
                if page_received < page_closed:
                    return _closed("TEST_PAGE_RECEIPT_PRECEDES_CLOSED_WINDOW")
                if page_received > decision:
                    return _closed("HISTORICAL_PAGE_ARRIVED_AFTER_DECISION")
                checked += 1
        return {
            **out,
            "status": "SYNTHETIC_PAGES_WITHIN_LOCAL_DECISION_CUTOFF_ONLY",
            "reason": "PAGE_RECEIPT_IS_NOT_GENUINE_PER_BAR_FIRST_SEEN",
            "syntheticPagesAtOrBeforeDecision": True,
            "historicalPagesAvailableBySyntheticCutoff": True,
            "closedBidAskMtfLocalParity": True,
            "totalSealedPagesChecked": checked,
        }
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            OverflowError, AttributeError):
        return _closed("UNTRUSTED_OR_MISSING_SYNTHETIC_ARRIVAL_EVIDENCE")
