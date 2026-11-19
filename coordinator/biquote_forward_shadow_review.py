"""Private BiQuote forward-vault -> frozen V3 shadow analysis (offline).

No network, no broker, no orders, no market data in stdout. Actual archived
MID may be BID-seeded; only truly closed, contiguous bars are evaluated.
This is a *blocked signal research preview*, never a trade or paper admission.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys

from biquote_private_forward_vault import START, FRAMES_ORDER, inspect_vault_metadata, load_vault, _stamp
from biquote_quote_mid_parity import audit_closed_quote_mid_parity

UTC = dt.timezone.utc
MIN_CONTIGUOUS = 21
MAX_CONTIGUOUS = 48
WIDTH = {"M15": 900, "H1": 3600, "H4": 14400}
NODE = pathlib.Path(__file__).with_name("ultimate_four_stage_review.js")
NO_SOURCE_RIGHTS = [
    "UNDERLYING_BROKER_SESSION_UNVERIFIED",
    "BIQUOTE_MID_MAY_INCLUDE_BID_SEED",
    "HISTORICAL_BID_ASK_EXECUTION_COSTS_NOT_VERIFIED",
    "GC_DXY_YIELDS_CALENDAR_NEWS_AND_LICENSED_ORDERFLOW_UNVERIFIED",
    "FORWARD_PROFITABILITY_UNTESTED",
]
BASE = {
    "mode": "BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY",
    "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
    "tradeEligible": False, "researchEligible": False,
    "brokerOrdersSent": 0, "sourceRequestsMade": 0,
    "historicalBidAskExecutionVerified": False,
    "independentMacroVerified": False,
    "independentBrokerRightsVerified": False,
    "brokerSessionCalendarVerified": False,
    "profitabilityProven": False, "signalReady": False,
    "brokerPricesExposed": False,
}


def tail_contiguous(rows: object, width: int) -> list[dict]:
    """Return only a strictly closed, unmodified contiguous suffix."""
    if not isinstance(rows, list):
        return []
    tail = []
    last = None
    for row in reversed(rows):
        if not isinstance(row, dict) or set(row) != {
            "openTime", "open", "high", "low", "close"
        }:
            break
        try:
            t = _stamp(row["openTime"])
        except (ValueError, TypeError):
            break
        if last is not None and (last - t).total_seconds() != width:
            break
        o, h, l, c = (row[k] for k in ("open", "high", "low", "close"))
        # The vault's hash proves local consistency, NOT market data quality.
        if any(type(v) not in (int, float) or not (0 < v < 1e8)
               for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
            break
        tail.append({"datetime": row["openTime"], "open": o, "high": h, "low": l, "close": c})
        last = t
        if len(tail) >= MAX_CONTIGUOUS:
            break
    return list(reversed(tail))


def overlaps_match(frames: dict[str, list[dict]]) -> dict:
    """Check source-observed fully covered H1/H4 closes using M15, not inferred bars."""
    m15={b["datetime"]: b for b in frames["M15"]}
    out={}
    for tf, n in (("H1",4),("H4",16)):
        verified=0
        mismatches=0
        for higher in frames[tf]:
            start=_stamp(higher["datetime"])
            sub=[m15.get((start+dt.timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M:%SZ"))
                 for i in range(n)]
            if any(x is None for x in sub):
                continue  # unknown coverage, NEVER treat as matched
            expected={"open":sub[0]["open"],
                      "high":max(b["high"] for b in sub),
                      "low":min(b["low"] for b in sub),
                      "close":sub[-1]["close"]}
            verified+=1
            if any(abs(expected[k]-higher[k])>max(0.00001,abs(higher[k])*1e-8)
                   for k in expected):
                mismatches+=1
        out[tf]={"fullyCoveredCompared":verified,
                 "fullyCoveredDisagreed":mismatches}
    return out


def shadow_review(dirname: str | pathlib.Path, *, runner=None,
                  now_utc: dt.datetime | None = None,
                  vault_metadata=None, sealed_vault=None) -> dict:
    """Read existing private vault; never write files or call an external feed.

    Only an in-process offline Node child sees OHLC. The caller receives
    counts, timestamps, blockers, and an unapproved technical *watch* state.
    """
    safe = {**BASE, "technicalWatch": "NONE", "approvedDirection": "NONE",
            "entry": None, "stopLoss": None, "takeProfit": None,
            "paperPerformance": None, "holdoutStartsUTC": "2026-11-18T00:00:00Z",
            "reasonCodes": [*NO_SOURCE_RIGHTS], "frames": {},
            "researchWarmup": {
                "minimumClosedBarsEachFrame": MIN_CONTIGUOUS,
                "minimumPerfectH4Hours": MIN_CONTIGUOUS * WIDTH["H4"] // 3600,
                "single24HourWindowEnoughForH4": False,
                "additionalExplicitlyApprovedCaptureRequired": True,
                "brokerSessionGapClassificationVerified": False,
                "paperTradingAdmissible": False,
            }}
    # One atomic sealed-vault snapshot may be shared by authenticated status,
    # offline V3 shadow and four-stage gate. In standalone mode load it once.
    # The price-bearing archive NEVER enters the HTTP response.
    if (vault_metadata is None) != (sealed_vault is None):
        raise ValueError("INCOMPLETE_SEALED_VAULT_SNAPSHOT")
    if sealed_vault is None:
        archive = load_vault(dirname)
        metadata = inspect_vault_metadata(archive, now_utc=now_utc)
    else:
        archive, metadata = sealed_vault, vault_metadata
        if (not isinstance(archive, dict) or
                archive.get("source") != "BIQUOTE_UNVERIFIED_UPSTREAM_MT5" or
                archive.get("schema") != 1 or
                not isinstance(metadata, dict) or
                metadata.get("status") != "PRIVATE_FORWARD_VAULT_METADATA_ONLY" or
                metadata.get("signal") != "WAIT" or
                metadata.get("executable") is not False or
                metadata.get("paperOrdersAllowed") is not False or
                metadata.get("noTradingAdmission") is not True or
                metadata.get("lastImportedUTC") != archive.get("lastImportedUTC") or
                not isinstance(archive.get("closed"),dict) or
                not isinstance(archive.get("quoteObservations"),list) or
                metadata.get("quoteSamples") != len(archive["quoteObservations"]) or
                any(not isinstance(archive["closed"].get(tf),list) or
                    metadata.get("counts",{}).get(tf) != len(archive["closed"][tf])
                    for tf in FRAMES_ORDER)):
            raise ValueError("INCONSISTENT_SEALED_VAULT_SNAPSHOT")
    rows = archive["closed"]
    received = archive["lastImportedUTC"]
    for tf in FRAMES_ORDER:
        width = WIDTH[tf]
        continuous = tail_contiguous(rows[tf], width)
        safe["frames"][tf] = {
            "persistedClosed": metadata["counts"][tf],
            "contiguousClosed": len(continuous),
            "lastClosedUTC": metadata["forwardCoverage"][tf]["lastClosedUTC"],
            "unclassifiedGapPairs": metadata["forwardCoverage"][tf]["unclassifiedGapPairs"],
            "neededContiguous": MIN_CONTIGUOUS,
            "additionalContiguousNeeded": max(0, MIN_CONTIGUOUS - len(continuous)),
        }
    # Do not confuse total saved candles with the most recent strictly
    # contiguous warmup. A vendor daily-pause hypothesis is not a verified
    # MT5 broker calendar and NEVER permits bridging missing OHLC candles.
    reference=metadata.get("gapReference",{})
    if (not isinstance(reference,dict) or
            reference.get("mode")!="BIQUOTE_PRIVATE_REFERENCE_GAP_COUNTS_ONLY" or
            reference.get("status")!="REFERENCE_ONLY_NOT_BROKER_VERIFIED" or
            reference.get("independentBrokerCalendarVerified") is not False or
            reference.get("sourceRightsVerified") is not False or
            reference.get("allGapsRemainUnclassified") is not True):
        safe["reasonCodes"].append("FORWARD_GAP_REFERENCE_UNAVAILABLE")
        return safe
    continuity={}
    for tf in FRAMES_ORDER:
        item=reference.get("frames",{}).get(tf,{})
        history=metadata["forwardCoverage"][tf]
        total=safe["frames"][tf]["persistedClosed"]
        tail=safe["frames"][tf]["contiguousClosed"]
        missing=item.get("unclassifiedMissingSlots")
        pause=item.get("vendorPauseCandidateSlotsNotVerified")
        outside=item.get("outsideVendorReferenceSlots")
        unknown=item.get("unknownReferenceSlots")
        pairs=item.get("gapPairs")
        if (any(type(v) is not int or v<0 or v>4500000
                for v in (missing,pause,outside,unknown,pairs)) or
                pause+outside+unknown!=missing or
                item.get("persistedClosed")!=total or
                history.get("closedBars")!=total or
                history.get("unclassifiedMissingSlots")!=missing or
                history.get("unclassifiedGapPairs")!=pairs or
                not 0<=tail<=min(total,48)):
            safe["reasonCodes"].append("FORWARD_GAP_REFERENCE_COUNTER_MISMATCH")
            return safe
        continuity[tf]={
            "persistedClosed":total,
            "strictLatestContiguous":tail,
            "remainingUntil21":max(0,MIN_CONTIGUOUS-tail),
            "unclassifiedMissingSlots":missing,
            "vendorPauseCandidatesNotVerified":pause,
            "outsideVendorReferenceSlots":outside,
            "unknownReferenceSlots":unknown,
            "lastRunAfterUnclassifiedGap":pairs>0 and tail<total,
        }
    safe["warmupContinuity"]={
        "status":"STRICT_RAW_CLOSED_BARS_BROKER_CALENDAR_UNVERIFIED",
        "signal":"WAIT","paperOrdersAllowed":False,
        "brokerCalendarVerified":False,"sourceRightsVerified":False,
        "gapBridgingAllowed":False,
        "frames":continuity,
    }
    # Independent OFFLINE geometry diagnostic, even during H4 warmup.
    # Inspect only the tail of actual, closed, hash-sealed M15/H1/H4 bars.
    # Count fully covered comparisons separately from uncovered higher bars.
    # This NEVER certifies a broker session, source license or a trading setup.
    checked={tf:tail_contiguous(rows[tf],WIDTH[tf]) for tf in FRAMES_ORDER}
    parity=overlaps_match(checked)
    diagnostics={}
    for higher_tf in ("H1","H4"):
        matches=parity[higher_tf]["fullyCoveredCompared"]
        disagreements=parity[higher_tf]["fullyCoveredDisagreed"]
        observed=len(checked[higher_tf])
        if not 0<=disagreements<=matches<=observed:
            safe["reasonCodes"].append("ARCHIVED_CROSS_FRAME_DIAGNOSTIC_UNAVAILABLE")
            return safe
        diagnostics[higher_tf]={
            "higherClosedExamined":observed,
            "fullyCoveredCompared":matches,
            "fullyCoveredDisagreed":disagreements,
            "notFullyCovered":observed-matches,
        }
    safe["diagnosticCrossFrameParity"]={
        "status":"CLOSED_ARCHIVE_GEOMETRY_ONLY_NOT_TRADE_PROOF",
        "frames":diagnostics,
        "sourceRightsVerified":False,
        "brokerCalendarVerified":False,
        "paperOrdersAllowed":False,
        "signal":"WAIT",
    }
    if any(diagnostics[tf]["fullyCoveredDisagreed"] for tf in ("H1","H4")):
        safe["reasonCodes"].append("ARCHIVED_CROSS_FRAME_OHLC_DISAGREEMENT")
        return safe
    # Independent stored BID/ASK snapshots must NOT contradict same-feed
    # closed MID candle ranges before frozen V3 can show a technical watch.
    # Recalculate from the ONE sealed snapshot: precomputed caller-supplied
    # metadata is not proof, and a provider cannot approve its own feed.
    # Missing comparable samples remain unverified; this is NOT a trade gate.
    quote_mid = audit_closed_quote_mid_parity(archive)
    if metadata.get("quoteCandleMidGeometry") != quote_mid:
        safe["reasonCodes"].append("QUOTE_CANDLE_MID_METADATA_MISMATCH")
        return safe
    if quote_mid["status"] == "INVALID_ARCHIVE_WAIT":
        safe["reasonCodes"].append("QUOTE_CANDLE_MID_GEOMETRY_INVALID")
        return safe
    if quote_mid["status"] == "OBSERVED_MID_OUTSIDE_CLOSED_OHLC":
        safe["reasonCodes"].append("QUOTE_MID_OUTSIDE_CLOSED_CANDLE_RANGE")
        return safe
    if received is None or not archive["quoteObservations"]:
        safe["reasonCodes"].append("NO_POST_HOLDOUT_CAPTURE")
        return safe
    receipt = _stamp(received)
    if receipt < START:
        safe["reasonCodes"].append("FORWARD_TIME_BOUNDARY_FAILED")
        return safe
    clock = dt.datetime.now(UTC) if now_utc is None else now_utc
    if not isinstance(clock, dt.datetime) or clock.tzinfo is None or (
        clock.utcoffset() != dt.timedelta(0)):
        safe["reasonCodes"].append("CURRENT_UTC_CLOCK_UNVERIFIED")
        return safe
    freshness = (clock - receipt).total_seconds()
    # A recorded archive can be analyzed offline, but it MUST NOT become a
    # 'current' BUY/SELL watch after the collection worker stops or sleeps.
    # No forward/future market data can be accepted as the present either.
    if freshness < 0 or freshness > 300:
        safe["reasonCodes"].append("ARCHIVED_CAPTURE_STALE_OR_FUTURE_VS_NOW")
        return safe
    quote = archive["quoteObservations"][-1]
    if not isinstance(quote, dict) or quote.get("observedUTC") != received:
        safe["reasonCodes"].append("NO_CO_TIMED_BID_ASK_QUOTE")
        return safe
    tick = _stamp(quote["tickUTC"])
    if not 0 <= (receipt - tick).total_seconds() <= 30:
        safe["reasonCodes"].append("QUOTE_STALE_AT_RECORDED_DECISION")
        return safe
    if any(safe["frames"][tf]["contiguousClosed"] < MIN_CONTIGUOUS
           for tf in FRAMES_ORDER):
        safe["reasonCodes"].append("INSUFFICIENT_CONTIGUOUS_CLOSED_H4_H1_M15")
        # A single 24-hour forward run can contain at most six closed
        # four-hour candles. No historical/pre-holdout candles may be silently
        # imported to make this look ready. Another capture requires consent.
        if safe["frames"]["H4"]["contiguousClosed"] < MIN_CONTIGUOUS:
            safe["reasonCodes"].append("ONE_DAY_FORWARD_CAPTURE_CANNOT_WARM_UP_H4")
        return safe
    closed_frames=checked
    safe["comparedCrossFrames"]=parity
    if (any(parity[tf]["fullyCoveredCompared"] < 1 or
            parity[tf]["fullyCoveredDisagreed"] > 0
            for tf in ("H1","H4"))):
        safe["reasonCodes"].append("FORWARD_CROSS_FRAME_PARITY_NOT_PROVEN")
        return safe
    # An entirely fresh BID/ASK tick can coexist with a stalled candle
    # endpoint. Never show even a V3 *technical watch* from such an archive.
    # Thresholds (2x frame width) are conservative diagnostics, NOT an
    # independent broker/session calendar or proof of feed entitlements.
    frame_health=metadata.get("closedFrameFreshness")
    if (not isinstance(frame_health,dict) or
        frame_health.get("mode")!="BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY" or
        frame_health.get("status")!="AGE_COUNTS_ONLY_UNVERIFIED" or
        frame_health.get("signal")!="WAIT" or
        frame_health.get("executable") is not False or
        frame_health.get("paperOrdersAllowed") is not False or
        frame_health.get("sourceQualified") is not False or
        frame_health.get("brokerCalendarVerified") is not False or
        frame_health.get("gapBridgingAllowed") is not False):
        safe["reasonCodes"].append("FROZEN_V3_CLOSED_BAR_AGE_UNAVAILABLE")
        return safe
    frames_health=frame_health.get("frames")
    if (not isinstance(frames_health,dict) or
        set(frames_health)!=set(FRAMES_ORDER) or
        any(not isinstance(frames_health[tf],dict) or
            frames_health[tf].get("status")!="RECENT_UNVERIFIED" or
            type(frames_health[tf].get("ageSeconds")) is not int or
            not 0<=frames_health[tf]["ageSeconds"]<=2*WIDTH[tf]
            for tf in FRAMES_ORDER)):
        safe["reasonCodes"].append("FROZEN_V3_CLOSED_BAR_STALE_OR_UNVERIFIED")
        return safe
    # Secondary strict UTC-as-of gate: a new BID/ASK tick does not prove
    # that the latest CLOSED candles caught up. The archive's 2-frame
    # freshness diagnostic is for collection monitoring ONLY; the actual
    # frozen V3 checkFrame uses at most ONE frame of age at the decision.
    # Recheck here independently even if a test runner lies about Node's
    # dataGeometry status. Never bridge session gaps or synthesize candles.
    if any(not checked[tf] or
           not 0 <= (receipt - (
               _stamp(checked[tf][-1]["datetime"]) +
               dt.timedelta(seconds=WIDTH[tf])
           )).total_seconds() <= WIDTH[tf]
           for tf in FRAMES_ORDER):
        safe["reasonCodes"].append("FROZEN_V3_AS_OF_CLOSED_BAR_NOT_RECENT")
        return safe
    packet = {"dataOrigin": "BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER",
              "snapshot": {
                  "asOfUTC": received,
                  "frames": closed_frames,
                  "feeds": {},   # NEVER forge GC/DXY/yields/news/order flow.
                  "spread": quote["spread"],
                  # There is no verified broker lot/commission contract.
                  "risk": {"killSwitch": True, "activeTrades": 0},
              }}
    if runner is None:
        runner = lambda source: subprocess.run(
            ["node", str(NODE)], input=json.dumps(source, allow_nan=False),
            text=True, capture_output=True, check=True, timeout=12,
        ).stdout
    try:
        output = json.loads(runner(packet))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        safe["reasonCodes"].append("OFFLINE_FROZEN_ENGINE_UNAVAILABLE")
        return safe
    if not isinstance(output, dict) or output.get("signal") != "WAIT" or (
        output.get("executable") is not False or
        output.get("paperOrdersAllowed") is not False or
        output.get("liveOrdersAllowed") is not False or
        output.get("researchEligible") is not False or
        output.get("hypotheticalSyntheticPlan") is not None or
        output.get("dataOrigin") != "BIQUOTE_ARCHIVED_UNVERIFIED_NO_PAPER"
    ):
        safe["reasonCodes"].append("SHADOW_OUTPUT_CONTRACT_REJECTED")
        return safe
    stages = output.get("stages")
    if (not isinstance(stages, dict) or
        stages.get("data", {}).get("status") != "GEOMETRY_ONLY" or
        stages.get("analysis", {}).get("status") != "FROZEN_ENGINE_EVALUATED"):
        safe["reasonCodes"].append("FROZEN_V3_GEOMETRY_NOT_VERIFIED")
        return safe
    direction = stages.get("analysis", {}).get("technicalCandidate")
    if direction not in ("BUY", "SELL", "NONE"):
        safe["reasonCodes"].append("UNEXPECTED_TECHNICAL_CANDIDATE")
        return safe
    safe["technicalWatch"] = direction  # only a technical observation; never a trade
    safe["engineReview"] = "FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS"
    safe["reasonCodes"].append("NO_REAL_SIGNAL_WITHOUT_INDEPENDENT_CONTEXT_AND_RISK")
    return safe


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-dir", required=True)
    args = parser.parse_args()
    # Never print raw exception text (may contain sensitive paths).
    try:
        result = shadow_review(args.vault_dir)
    except (OSError, ValueError, TypeError, KeyError):
        result = {**BASE, "technicalWatch": "NONE", "approvedDirection": "NONE",
                  "reasonCodes": ["VAULT_UNAVAILABLE_OR_TAMPERED"],
                  "entry": None, "stopLoss": None, "takeProfit": None}
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
