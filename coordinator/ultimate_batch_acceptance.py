"""Single read-only handoff across the four unfinished Gold Precision stages.

Never imports a broker, fetches a feed, arms a scheduled worker, creates a
paper position or reads prices into its report. Inspect only a private vault
and an explicitly supplied finished 24h metadata report. A green offline
test is not a live data, license, trade-quality or profitability attestation.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib

from biquote_24h_final_verdict import verdict
from biquote_private_forward_vault import FRAMES_ORDER, inspect_vault_metadata, load_vault
from biquote_forward_shadow_review import shadow_review
from paper_admission_gate import assess_biquote_paper_gate
from private_forward_capacity_preflight import capacity_readiness

UTC=dt.timezone.utc
BASE={
    "mode":"GOLD_PRECISION_FOUR_STAGE_BATCH_READONLY_V1",
    "signal":"WAIT", "executable":False, "paperOrdersAllowed":False,
    "liveOrdersAllowed":False, "tradeEligible":False, "signalReady":False,
    "researchEligible":False, "brokerOrdersSent":0, "providerRequestsMade":0,
    "archiveWritesMade":0, "paperLedgerWritesMade":0,
    "brokerFeedRightsIndependentlyVerified":False,
    "brokerSessionCalendarIndependentlyVerified":False,
    "historicalBidAskExecutionVerified":False,
    "gcOrderFlowIndependentlyVerified":False,
    "macroFeedsIndependentlyVerified":False,
    "outOfSampleNetExpectancyProven":False,
    "rawMarketPricesExposed":False,
}
FRAME_CODES={"M15":"M15","H1":"H1","H4":"H4"}

def review_batch(vault_dir, *, final_report=None, now_utc=None, shadow_runner=None,
                 vault_metadata=None, shadow_status=None):
    """All four workstreams, one fail-closed report; offline, NO disk writes."""
    result={**BASE,"stages":{},"reasonCodes":[]}
    # Stage 1: qualified source vs completed observation of an unqualified feed.
    v=verdict(final_report)
    source_ok=(v.get("status")=="REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE"
               and v.get("httpFailedSamples")==0
               and v.get("totalStructuralAuditPassed")==720
               and v.get("independentQuoteAgeMaximumSeconds") is not None
               and 0<=v["independentQuoteAgeMaximumSeconds"]<=30
               and v.get("h1OHLCDisagreements")==0
               and v.get("h4OHLCDisagreements")==0
               and v.get("unclassifiedCoverageSamples")==0)
    # Even hypothetically ideal quality is not independent broker rights.
    source_reasons=v.get("reasonCodes",["REPORT_NOT_VERIFIED"])
    result["stages"]["data"]={
        "status":"SAMPLED_SOURCE_QUALITY_CHECKED_NOT_LICENSED" if source_ok
                 else "SOURCE_NOT_QUALIFIED",
        "reviewWindowCompleted":v.get("status")=="REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE",
        "fullSampleCount":v.get("samplesObserved",0),
        "httpOkSamples":v.get("httpOkSamples",0),
        "httpFailedSamples":v.get("httpFailedSamples"),
        "fullStructuralPasses":v.get("totalStructuralAuditPassed"),
        "maximumSampledQuoteAgeSeconds":v.get("independentQuoteAgeMaximumSeconds"),
        "sourceRightsVerified":False,"independentBrokerCalendarVerified":False,
        "liveProviderConnected":False,"blockers":list(source_reasons)[:28]
    }
    # Stage 2: protected prospective data archive, no new provider calls.
    try:
        # Coordinator already reads these inside a protected status request.
        # Reuse that same result instead of reloading disk and running V3 a
        # second time; standalone CLI still reads directly.
        if (vault_metadata is None) != (shadow_status is None):
            raise ValueError("INCOMPLETE_PRECOMPUTED_STATUS")
        if vault_metadata is None:
            # Standalone CLI and tests also use ONE SHA-checked private vault
            # read. No race between metadata and shadow diagnostics when an
            # atomic writer replaces the archive during evaluation.
            sealed=load_vault(vault_dir)
            m=inspect_vault_metadata(sealed,now_utc=now_utc)
            sh=shadow_review(
                vault_dir,runner=shadow_runner,now_utc=now_utc,
                vault_metadata=m,sealed_vault=sealed)
        else:
            m=vault_metadata
            sh=shadow_status
            if (not isinstance(m,dict) or
                m.get("status")!="PRIVATE_FORWARD_VAULT_METADATA_ONLY" or
                m.get("signal")!="WAIT" or m.get("executable") is not False or
                m.get("paperOrdersAllowed") is not False or
                m.get("tradeSignalReady") is not False or
                not isinstance(sh,dict) or
                sh.get("mode")!="BIQUOTE_PRIVATE_FORWARD_V3_SHADOW_ONLY" or
                sh.get("signal")!="WAIT" or
                sh.get("executable") is not False or
                sh.get("paperOrdersAllowed") is not False or
                sh.get("signalReady") is not False or
                sh.get("approvedDirection")!="NONE"):
                raise ValueError("FORGED_PRECOMPUTED_STATUS")
        counts={tf:m["counts"][tf] for tf in FRAMES_ORDER}
        # V3 preview is capped at 48 OHLC bars for bounded analysis.
        # 50-bar paper-horizon COUNTS use private sealed full-tail metadata.
        tails={tf:m["forwardCoverage"][tf]["latestContiguousBars"]
               for tf in FRAMES_ORDER}
        capacity=capacity_readiness(m)
        # Stage 2 never promotes source or technical readiness. Require
        # cross-file counter consistency before showing continuity progress.
        for tf in FRAMES_ORDER:
            details=sh["frames"][tf]
            coverage=m["forwardCoverage"][tf]
            if (type(tails[tf]) is not int or
                not 0<=tails[tf]<=counts[tf] or
                details.get("contiguousClosed")!=min(tails[tf],48) or
                details.get("persistedClosed")!=counts[tf] or
                details.get("neededContiguous")!=21 or
                coverage.get("closedBars")!=counts[tf] or
                type(coverage.get("unclassifiedGapPairs")) is not int or
                not 0<=coverage["unclassifiedGapPairs"]<=counts[tf] or
                type(coverage.get("unclassifiedMissingSlots")) is not int or
                not 0<=coverage["unclassifiedMissingSlots"]<=4500000):
                raise ValueError("INCONSISTENT_STAGE2_PRIVATE_CLOSED_HISTORY")
        # Stage 3 is a strictly read-only frozen V3 qualification.
        # A precomputed "evaluated" claim is only accepted when it agrees
        # with 21 contiguous bars and independently computed M15/H1/H4
        # overlap counts. These comparisons are NOT broker entitlement.
        evaluated_claim=sh.get("engineReview")=="FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS"
        if evaluated_claim:
            parity=sh.get("comparedCrossFrames")
            if any(tails[tf]<21 for tf in FRAMES_ORDER) or not isinstance(parity,dict):
                raise ValueError("INCONSISTENT_STAGE3_V3_WARMUP")
            for tf in ("H1","H4"):
                evidence=parity.get(tf)
                if (not isinstance(evidence,dict) or
                    type(evidence.get("fullyCoveredCompared")) is not int or
                    evidence["fullyCoveredCompared"]<1 or
                    type(evidence.get("fullyCoveredDisagreed")) is not int or
                    evidence["fullyCoveredDisagreed"]!=0):
                    raise ValueError("INCONSISTENT_STAGE3_FRAME_PARITY")
        stage2_frames={tf:{
            "persistedClosed":counts[tf],
            "contiguousClosed":tails[tf],
            "remainingUntil21":max(0,21-tails[tf]),
            "unclassifiedGapPairs":m["forwardCoverage"][tf]["unclassifiedGapPairs"],
            "unclassifiedMissingSlots":m["forwardCoverage"][tf]["unclassifiedMissingSlots"]
        } for tf in FRAMES_ORDER}
        archive_status="FORWARD_CAPTURE_PRESENT_UNVERIFIED" if any(counts.values()) else "NO_FORWARD_CAPTURE"
    except (OSError,ValueError,TypeError,KeyError):
        m=None
        sh=None
        counts={tf:0 for tf in FRAMES_ORDER}
        tails={tf:0 for tf in FRAMES_ORDER}
        archive_status="PRIVATE_VAULT_NOT_READABLE"
        stage2_frames={tf:{
            "persistedClosed":0,"contiguousClosed":0,
            "remainingUntil21":21,
            "unclassifiedGapPairs":0,"unclassifiedMissingSlots":0
        } for tf in FRAMES_ORDER}
        capacity=None
    stage2_status=("WAIT_PRIVATE_ARCHIVE_UNAVAILABLE" if m is None else
                   "WAIT_NO_FORWARD_CLOSED_BARS" if not any(counts.values()) else
                   "WAIT_CONTIGUOUS_CLOSED_BAR_WARMUP" if any(
                       tails[tf]<21 for tf in FRAMES_ORDER) else
                   "WAIT_INDEPENDENT_SOURCE_RIGHTS_AND_CALENDAR")
    result["stages"]["archive"]={
        "status":archive_status,
        "closedCounts":counts,
        "consecutiveClosedCounts":tails,
        "stage2Status":stage2_status,
        "stage2Frames":stage2_frames,
        "stage2SourceVerified":False,
        "stage2SessionCalendarVerified":False,
        "stage2EligibleForPaper":False,
        "capacityStatus":capacity["status"] if capacity else "CAPACITY_METADATA_UNAVAILABLE",
        "quoteSamplesRemaining":capacity["quoteSamplesRemaining"] if capacity else None,
        "quoteSamplesHardCap":capacity["quoteSamplesHardCap"] if capacity else None,
        "archiveCapacityExhausted":capacity["status"]=="CAPACITY_LIMIT_REACHED" if capacity else True,
        "automaticQuoteDeletionAllowed":False,
        "minimumNeededEach":21,
        "lastImportedUTC":m.get("lastImportedUTC") if m else None,
        "privateStorageVerified":m is not None and any(counts.values()),
        "dataSourceIndependentlyAuthenticated":False,
        "sessionGapsProven":False,
        "holdoutProfitabilityProven":False
    }
    # Stage 3: frozen V3 can show TECHNICAL ONLY after all closed frames,
    # but cannot ever authorize BUY/SELL or include a real entry/SL/TP.
    watch=sh.get("technicalWatch") if isinstance(sh,dict) else "NONE"
    if watch not in ("BUY","SELL","NONE"):watch="NONE"
    evaluated=(isinstance(sh,dict) and
               sh.get("engineReview")=="FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS")
    analysis_codes=sh.get("reasonCodes",[]) if isinstance(sh,dict) else ["VAULT_UNAVAILABLE_OR_TAMPERED"]
    ready_frames=sum(1 for tf in FRAMES_ORDER if tails[tf]>=21)
    stage3_status=("WAIT_ARCHIVE_UNAVAILABLE" if m is None else
                   "WAIT_CLOSED_BAR_WARMUP" if ready_frames<3 else
                   "WAIT_INDEPENDENT_FEEDS_AND_RIGHTS" if evaluated else
                   "WAIT_SHADOW_FRESHNESS_OR_PARITY")
    stage3_safe={
        "status":stage3_status,"signal":"WAIT",
        "minimumContiguousClosedEachFrame":21,
        "framesWithWarmup":ready_frames,
        "h4ContiguousClosed":tails["H4"],
        "h4RemainingUntil21":max(0,21-tails["H4"]),
        "frozenV3Observed":evaluated,
        "crossFrameParityObserved":evaluated,
        "brokerRightsVerified":False,
        "brokerSessionCalendarVerified":False,
        "independentMacroOrderFlowVerified":False,
        "paperOrdersAllowed":False,"liveOrdersAllowed":False,
    }
    result["stages"]["analysis"]={
        "status":"FROZEN_V3_TECHNICAL_OBSERVATION_ONLY" if evaluated else "WAIT_CLOSED_DATA_OR_CONTEXT",
        "stage3":stage3_safe,
        "technicalWatch":watch if evaluated else "NONE",
        "approvedDirection":"NONE", "entry":None,
        "stopLoss":None,"takeProfit":None, "winProbability":None,
        "independentContextVerified":False,
        "blockers":list(analysis_codes)[:25]
    }
    # Stage 4: existing paper admission/cost engine; no positions, orders,
    # fills or fabricated equity curve, regardless of synthetic V3 output.
    paper=assess_biquote_paper_gate(
        {"ohlcStructuralChecksPassed":source_ok},
        {"status":"BLOCKED"},counts,tails)
    result["stages"]["paper"]={
        "status":"BLOCKED", "paperOrdersAllowed":False,
        "paperLedgerOpened":False,"sampleTradesCreated":0,
        "brokerCostsVerified":False,"riskApproved":False,
        "forwardNetPerformanceEstablished":False,
        "historyReadiness":paper["historyReadiness"],
        "blockers":list(paper["reasonCodes"])[:18],
        "costBlockers":list(paper["costReadiness"]["reasonCodes"])[:12]
    }
    result["stages"]["context"]={
        "status":"INDEPENDENT_SOURCE_CONFIRMATIONS_REQUIRED",
        "DXY":False,"US02Y":False,"US10Y":False,"GC":False,
        "calendar":False,"headlines":False,"licensedOrderFlow":False
    }
    # One owner-only completion checklist for ALL unfinished stages.
    # Derive blockers exclusively from observed sealed-bar counters and
    # unverified source/risk flags; no simulated profit or broker authority.
    missing={tf:max(0,21-tails[tf]) for tf in FRAMES_ORDER}
    paper_missing={tf:max(0,50-tails[tf]) for tf in FRAMES_ORDER}
    blockers=[]
    if archive_status=="PRIVATE_VAULT_NOT_READABLE":
        blockers.append("PRIVATE_VAULT_UNREADABLE")
    elif archive_status=="NO_FORWARD_CAPTURE":
        blockers.append("NO_POST_HOLDOUT_CLOSED_CANDLES")
    for tf in FRAMES_ORDER:
        if missing[tf]:
            blockers.append("STRICT_"+tf+"_CLOSED_WARMUP_INCOMPLETE")
    if any(paper_missing.values()):
        blockers.append("STRICT_CONTIGUOUS_PAPER_HISTORY_50_BARS_INCOMPLETE")
    blockers.extend([
        "UNDERLYING_BROKER_MARKET_DATA_RIGHTS_UNCONFIRMED",
        "BROKER_XAUUSD_SESSION_DST_UNCONFIRMED",
        "GC_TRADES_MBO_MBP10_LICENSING_NOT_ESTABLISHED",
        "DXY_US02Y_US10Y_AND_EVENT_CONTEXT_NOT_INDEPENDENTLY_LIVE",
        "EXECUTION_BID_ASK_SPREAD_SLIPPAGE_FEES_UNVERIFIED",
        "OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN",
    ])
    result["completionAudit"]={
        "mode":"GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1",
        "status":"WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA",
        "signal":"WAIT","executable":False,
        "paperOrdersAllowed":False,"liveOrdersAllowed":False,
        "providerRequestsMade":0,"brokerOrdersSent":0,
        "independentMarketRightsVerified":False,
        "brokerSessionDSTVerified":False,
        "GCOrderFlowLicensed":False,
        "independentMacroFeedsVerified":False,
        "executionCostsVerified":False,
        "outOfSampleNetExpectancyVerified":False,
        "archiveIntegrityObserved":archive_status=="FORWARD_CAPTURE_PRESENT_UNVERIFIED",
        "missingStrictClosedBarsUntil21":missing,
        "missingStrictContiguousBarsUntilPaper50":paper_missing,
        "paperHistoryCountFloorMet":all(v==0 for v in paper_missing.values()),
        "paperHistoryIndependentlyQualified":False,
        # Strict wall-clock contiguity is *not* the same as consecutive
        # broker-tradable candles. An undocumented daily pause or weekend
        # can reset raw-grid continuity; do not silently exempt any slot.
        "sessionWarmupRisk":{
            "mode":"STRICT_GRID_WARMUP_BROKER_CALENDAR_EVIDENCE_PENDING_V1",
            "status":"BROKER_SESSION_PROOF_REQUIRED",
            "signal":"WAIT","executable":False,
            "brokerCalendarVerified":False,
            "sessionAwareWarmupAllowed":False,
            "missingCandleBridgingAllowed":False,
            "futureContinuityGuaranteed":False,
            "rawGridOnly":True,
            "strictContiguous":tails,
            "unclassifiedGapPairs":{
                tf:stage2_frames[tf]["unclassifiedGapPairs"] for tf in FRAMES_ORDER},
            "missingStrictClosedUntil21":missing,
        },
        "remainingBlockerCodes":blockers,
    }
    union=source_reasons+analysis_codes+paper["reasonCodes"]
    result["reasonCodes"]=list(dict.fromkeys(x for x in union
        if isinstance(x,str) and x.isupper() and x.replace("_","").isalnum()))[:60]
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--vault-dir",required=True)
    parser.add_argument("--finished-report-file")
    args=parser.parse_args()
    report=None
    if args.finished_report_file:
        try:
            p=pathlib.Path(args.finished_report_file)
            if p.stat().st_size>48000:
                raise ValueError("REPORT_TOO_LARGE")
            report=json.loads(p.read_text(encoding="utf-8"))
        except (ValueError,OSError,TypeError):
            report=None
    output=review_batch(args.vault_dir,final_report=report)
    print(json.dumps(output,sort_keys=True,allow_nan=False))

if __name__=="__main__":
    main()
