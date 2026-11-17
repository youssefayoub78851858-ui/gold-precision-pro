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
from biquote_private_forward_vault import FRAMES_ORDER, inspect_metadata
from biquote_forward_shadow_review import shadow_review
from paper_admission_gate import assess_biquote_paper_gate

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
            m=inspect_metadata(vault_dir)
            sh=shadow_review(vault_dir,runner=shadow_runner,now_utc=now_utc)
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
        tails={tf:sh["frames"][tf]["contiguousClosed"] for tf in FRAMES_ORDER}
        archive_status="FORWARD_CAPTURE_PRESENT_UNVERIFIED" if any(counts.values()) else "NO_FORWARD_CAPTURE"
    except (OSError,ValueError,TypeError,KeyError):
        m=None
        sh=None
        counts={tf:0 for tf in FRAMES_ORDER}
        tails={tf:0 for tf in FRAMES_ORDER}
        archive_status="PRIVATE_VAULT_NOT_READABLE"
    result["stages"]["archive"]={
        "status":archive_status,
        "closedCounts":counts,
        "consecutiveClosedCounts":tails,
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
    result["stages"]["analysis"]={
        "status":"FROZEN_V3_TECHNICAL_OBSERVATION_ONLY" if evaluated else "WAIT_CLOSED_DATA_OR_CONTEXT",
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
        {"status":"BLOCKED"})
    result["stages"]["paper"]={
        "status":"BLOCKED", "paperOrdersAllowed":False,
        "paperLedgerOpened":False,"sampleTradesCreated":0,
        "brokerCostsVerified":False,"riskApproved":False,
        "forwardNetPerformanceEstablished":False,
        "blockers":list(paper["reasonCodes"])[:18],
        "costBlockers":list(paper["costReadiness"]["reasonCodes"])[:12]
    }
    result["stages"]["context"]={
        "status":"INDEPENDENT_SOURCE_CONFIRMATIONS_REQUIRED",
        "DXY":False,"US02Y":False,"US10Y":False,"GC":False,
        "calendar":False,"headlines":False,"licensedOrderFlow":False
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
