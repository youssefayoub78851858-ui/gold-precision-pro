"""Sealed synthetic Capital archive -> existing XAU/USD research intake rehearsal.

No HTTP, session keys, live broker feeds, credentials, market rights,
Render file mutations, real paper fills, or orders. The single fixture is
intentionally unlicensed; this bridge cannot promote it to real research.

It proves the *interface* between three previously tested local components:
private sealed BID+ASK bars, page-level arrival cutoff, and the existing
source-policy / research engine intake. Raw OHLC never leaves the function.
"""
from __future__ import annotations

import datetime as dt

from capital_demo_synthetic_archive_mtf_replay import (
    replay_saved_synthetic_mtf, _synthetic_response
)
from capital_demo_synthetic_arrival_cutoff import inspect_synthetic_arrival
from capital_demo_private_page_store import _directory, _path, _read_existing
from capital_demo_offline_adapter import RESOLUTIONS, _normalize_row
from xauusd_feed_gate import SourcePolicy, intake_payload
from xauusd_research_pipeline import run_research_pipeline

MODE = "CAPITAL_DEMO_SYNTHETIC_PRIVATE_RESEARCH_HANDOFF_V1"
MAP = {"M15": "15min", "H1": "1h", "H4": "4h"}
MAX_PAGES = 48
MAX_TOTAL_ROWS = 6000


def _wait(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "sealedPagesValidated": False, "arrivalCutoffChecked": False,
        "bidAskParityLocallyMatched": False,
        "syntheticIntakeShapeChecked": False,
        "syntheticPacketHadFullClosedFrameGeometry": False,
        "realSourceIntakeBlocked": True,
        "sourceRightsIndependentlyVerified": False,
        "independentBrokerSessionVerified": False,
        "genuineProviderQuotes": False,
        "actualNetworkEgressEnforced": False,
        "independentOffsiteBackupVerified": False,
        "enginesInvoked": False, "paperRecorderInvoked": False,
        "resultEligibleForResearch": False, "readyForPaperSignals": False,
        "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False, "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "syntheticClosedCounts": {"M15": 0, "H1": 0, "H4": 0},
    }


def inspect_sealed_to_research_gate(plan, private_dir, decision_utc):
    """Validate the offline integration; deny all real-source admission."""
    try:
        joined = replay_saved_synthetic_mtf(plan, private_dir)
        if (joined.get("status") != "SYNTHETIC_LOCAL_MTF_PARITY_VERIFIED_ONLY"
                or joined.get("locallyMatchedBidAskH1H4") is not True):
            return _wait("SEALED_BID_ASK_MTF_REPLAY_NOT_VERIFIED")
        arrival = inspect_synthetic_arrival(plan, private_dir, decision_utc)
        if (arrival.get("status") !=
                "SYNTHETIC_PAGES_WITHIN_LOCAL_DECISION_CUTOFF_ONLY"
                or arrival.get("historicalPagesAvailableBySyntheticCutoff") is not True):
            return _wait("SYNTHETIC_PAGE_ARRIVAL_CUTOFF_NOT_VERIFIED")
        requests = plan["requests"]
        page_total = sum(len(requests[name]) for name in RESOLUTIONS)
        if page_total < 3 or page_total > MAX_PAGES:
            return _wait("UNSAFE_REPLAY_PAGE_BOUND")
        d = _directory(private_dir)
        at = dt.datetime.fromisoformat(decision_utc.replace("Z", "+00:00"))
        assembled = {}
        receipts = []
        total = 0
        for frame, (_, seconds) in RESOLUTIONS.items():
            bars = []
            for chunk in requests[frame]:
                # Prior signed vault/replay checks prove sealed bytes.
                # This additional check preserves original first local
                # receipt timestamps, rather than forging a new one.
                label = {
                    "epic": "TEST.GOLD.EPIC",
                    "resolution": chunk["request"]["query"]["resolution"],
                    "startUTC": chunk["firstExpectedOpenUTC"],
                    "endExclusiveUTC": chunk["expectedEndExclusiveUTC"],
                }
                stored = _read_existing(_path(d, label))
                receipts.append(
                    dt.datetime.fromisoformat(
                        stored["firstLocalTestReceiptUTC"].replace("Z", "+00:00")
                    )
                )
                safe_page = _synthetic_response(chunk, d)["response"]
                for row in safe_page["prices"]:
                    stamp, bid, ask = _normalize_row(row, seconds, at)
                    if any(bid[name] > ask[name]
                           for name in ("open", "high", "low", "close")):
                        return _wait("CROSSED_SYNTHETIC_BID_ASK")
                    bars.append(bid)
            if (not bars or any(bars[i]["openTime"] >= bars[i+1]["openTime"]
                                for i in range(len(bars)-1))):
                return _wait("DUPLICATE_OR_OUT_OF_ORDER_ARCHIVE_ROWS")
            total += len(bars)
            assembled[MAP[frame]] = {
                "candles": bars,
                "expectedOpenTimes": [row["openTime"] for row in bars],
            }
        if total > MAX_TOTAL_ROWS:
            return _wait("EXCESSIVE_REHEARSAL_ROWS")
        # First-received timestamp is from the immutable synthetic page,
        # never reset to the decision time to make a stale packet look fresh.
        last_receipt = max(receipts).isoformat().replace("+00:00", "Z")
        packet = {
            "provider": "CAPITAL_COM_SYNTHETIC_FIXTURE",
            "instrument": "XAU/USD",
            "mode": "synthetic",
            "receivedUTC": last_receipt,
            "frames": assembled,
        }
        # Crucial: the actual production intake contract is exercised
        # with its default, completely unentitled policy. No permissions
        # can be supplied via the archive or caller.
        policy = SourcePolicy(expected_provider="CAPITAL_COM_SYNTHETIC_FIXTURE")
        shaped = intake_payload(packet, at, policy)
        # Call the existing research pipeline with simulation disabled:
        # it must NOT invoke V3/r2 or paper, even on valid synthetic data.
        downstream = run_research_pipeline(
            packet, at, policy, {}, allow_synthetic_simulation=False
        )
        # Also prove that merely renaming the identical synthetic bars as
        # "recorded" or "BID" cannot make them licensed/trusted.
        alleged_live = {**packet, "provider": "CAPITAL_COM_DEMO",
                        "mode": "recorded", "priceBasis": "BID"}
        rejected = intake_payload(
            alleged_live, at, SourcePolicy(expected_provider="CAPITAL_COM_DEMO")
        )
        if (rejected["status"] != "BLOCKED" or
                rejected["researchEligible"] is not False or
                downstream.get("engines") != {
                    "v3": "SKIPPED", "ultimateR2": "SKIPPED",
                    "diagnostics": "SKIPPED", "paper": "SKIPPED"
                } or downstream.get("researchEligible") is not False or
                downstream.get("signal") != "WAIT" or
                downstream.get("executable") is not False):
            return _wait("RESEARCH_GATE_UNEXPECTEDLY_ACCEPTED_UNTRUSTED_DATA")
        ret = _wait(
            "SYNTHETIC_RECEIPTS_AND_SOURCE_PERMISSIONS_NOT_INDEPENDENTLY_ATTESTED"
        )
        ret.update({
            "status": "SEALED_SYNTHETIC_HANDOFF_QUARANTINED_ONLY",
            "sealedPagesValidated": True,
            "arrivalCutoffChecked": True,
            "bidAskParityLocallyMatched": True,
            "syntheticIntakeShapeChecked": True,
            "syntheticPacketHadFullClosedFrameGeometry": (
                shaped["status"] == "SYNTHETIC_TEST_ONLY"
            ),
            "syntheticClosedCounts": {
                frame: len(assembled[MAP[frame]]["candles"])
                for frame in RESOLUTIONS
            }
        })
        return ret
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            IndexError, OverflowError):
        return _wait("UNTRUSTED_OR_MISSING_SEALED_SYNTHETIC_HANDOFF")


if __name__ == "__main__":
    raise SystemExit("OFFLINE_SYNTHETIC_RESEARCH_HANDOFF_ONLY")
