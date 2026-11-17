"""Validate the FINISHED BiQuote 24-hour review telemetry, without any feed access.

The telemetry is a *claim from a specific reviewer run*, not independent
market-data proof. This offline validator never prints raw prices, quotes,
candles, credentials or entitlement claims and never activates archives.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys

UTC=dt.timezone.utc
CATEGORIES=("UNCLASSIFIED_M15_COVERAGE_GAP","OHLC_PRICE_DISAGREEMENT",
            "OTHER_SOURCE_SHAPE_FAILURE","NO_STRUCTURAL_FAILURE","UNAVAILABLE")
SAFE={"signal":"WAIT","executable":False,"paperOrdersAllowed":False,
      "tradeEligible":False,"researchEligible":False,
      "providerRequestsMade":0,"brokerOrdersSent":0,
      "archiveEnabled":False,"archiveActivationAllowed":False,
      "independentBrokerRightsVerified":False,
      "sessionCalendarVerified":False,"profitabilityProven":False,
      "mode":"BIQUOTE_24H_REVIEW_VERDICT_OFFLINE"}

def _num(x,maximum):
    return type(x) is int and 0<=x<=maximum

def _utc(x):
    if not isinstance(x,str) or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z",x):
        raise ValueError("BAD_UTC")
    t=dt.datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.utcoffset()!=dt.timedelta(0):
        raise ValueError("BAD_UTC")
    return t

def verdict(report):
    """Fail closed on missing, forged, stale, or contradictory final record."""
    out={**SAFE,"status":"BLOCKED","reasonCodes":["REPORT_NOT_VERIFIED"],
         "samplesObserved":0,"missedSlots":720,"httpOkSamples":0,
         "h1OHLCDisagreements":None,"h4OHLCDisagreements":None,
         "unclassifiedCoverageSamples":None,"crossFramePriceParityProven":False,
         "forwardArchivalResearchNeedsSeparateApproval":True}
    if not isinstance(report,dict) or report.get("event")!="BIQUOTE_REVIEW24H_REPORT":
        return out
    if any(((report.get(k) is not expected) if type(expected) is bool
            else (report.get(k)!=expected)) for k,expected in (
        ("signal","WAIT"),("executable",False),
        ("researchEligible",False),("paperOrdersAllowed",False),
        ("orderEndpointsCalled",False),("profitabilityTestPerformed",False),
        ("marketSessionIndependentlyVerified",False),
        ("cloudIndependentRightsProven",False),
        ("providerSLAProven",False),("rawQuotesPersisted",False))):
        out["reasonCodes"]=["UNSAFE_OR_INCOMPLETE_FINAL_REPORT"]
        return out
    if (report.get("status")!="RESEARCH_ONLY_24H_OBSERVATION" or
        report.get("source")!="BIQUOTE_PUBLIC_READONLY" or
        report.get("plannedHours")!=24 or
        report.get("sampleIntervalSeconds")!=120 or
        report.get("plannedSamples")!=720 or
        report.get("maxPermittedRequests")!=2880):
        out["reasonCodes"]=["REVIEW_SCOPE_MISMATCH"]
        return out
    try:
        started=_utc(report.get("startedUTC"))
        last=_utc(report.get("observedAsOfUTC"))
    except (TypeError,ValueError):
        out["reasonCodes"]=["INVALID_REVIEW_UTC_WINDOW"]
        return out
    # Exact pre-authorized observed run, not any later or unowned report.
    if started!=dt.datetime(2026,11,16,19,45,tzinfo=UTC):
        out["reasonCodes"]=["REVIEW_RUN_START_UNEXPECTED"]
        return out
    completed=report.get("completed24hWindow") is True
    if not completed or last<started+dt.timedelta(hours=24):
        out["reasonCodes"]=["REVIEW_NOT_COMPLETED"]
        return out
    integer_fields={
        "samplesObserved":720,"missedOrSkippedSlots":720,
        "requestsAttempted":2880,"httpOkSamples":720,
        "httpFailedSamples":720,"auditShapePassedSamples":720,
        "marketOpenSamples":720,"providerStaleSamples":720,
        "crossFrameUnverifiedSamples":720,
        "h1FullyCoveredComparedAcrossSnapshots":1000000,
        "h4FullyCoveredComparedAcrossSnapshots":1000000,
        "h1DisagreementsAcrossSnapshots":1000000,
        "h4DisagreementsAcrossSnapshots":1000000,
        "h1UnclassifiedPartialAggregatesAcrossSnapshots":1000000,
        "h4UnclassifiedPartialAggregatesAcrossSnapshots":1000000,
    }
    # The actual 989699cd Render observer predates category and private
    # archival counters. Recognize this older exact schema, never infer
    # missing categories or pretend it already archived anything.
    new_fields=("geometryFailureClasses","privateArchiveAttempts",
                "privateArchiveSavedSnapshots","privateArchiveRejectedSnapshots",
                "privateArchiveNewClosedBars")
    legacy=all(k not in report for k in new_fields)
    modern=all(k in report for k in new_fields)
    if not (legacy or modern):
        out["reasonCodes"]=["MIXED_OR_UNKNOWN_REPORT_SCHEMA"]
        return out
    if modern:
        integer_fields.update({
            "privateArchiveAttempts":720,
            "privateArchiveSavedSnapshots":720,
            "privateArchiveRejectedSnapshots":720,
        })
    if any(not _num(report.get(k),maxval) for k,maxval in integer_fields.items()):
        out["reasonCodes"]=["INVALID_REPORT_COUNTERS"]
        return out
    n=report["samplesObserved"]
    missed=report["missedOrSkippedSlots"]
    ok=report["httpOkSamples"]
    failed=report["httpFailedSamples"]
    cats=report.get("geometryFailureClasses") if modern else None
    if (n+missed!=720 or ok+failed!=n or
        report["requestsAttempted"]>4*n or
        report["auditShapePassedSamples"]>ok or
        report["marketOpenSamples"]>ok or
        report["providerStaleSamples"]>ok or
        report["crossFrameUnverifiedSamples"]>ok or
        report["h1DisagreementsAcrossSnapshots"]>report["h1FullyCoveredComparedAcrossSnapshots"] or
        report["h4DisagreementsAcrossSnapshots"]>report["h4FullyCoveredComparedAcrossSnapshots"]):
        out["reasonCodes"]=["REPORT_COUNTER_CONTRADICTION_OR_UNEXPECTED_ARCHIVE"]
        return out
    if modern and (
        not isinstance(cats,dict) or set(cats)!=set(CATEGORIES) or
        any(not _num(cats[k],720) for k in CATEGORIES) or
        sum(cats.values())!=ok or
        report["privateArchiveSavedSnapshots"]>report["privateArchiveAttempts"] or
        report["privateArchiveRejectedSnapshots"]>report["privateArchiveAttempts"] or
        report["privateArchiveAttempts"]>n or
        report["privateArchiveSavedSnapshots"]>0 or
        not isinstance(report["privateArchiveNewClosedBars"],dict) or
        any(not _num(report["privateArchiveNewClosedBars"].get(tf),50000)
            for tf in ("M15","H1","H4")) or
        any(report["privateArchiveNewClosedBars"][tf]>0 for tf in ("M15","H1","H4"))):
        out["reasonCodes"]=["REPORT_COUNTER_CONTRADICTION_OR_UNEXPECTED_ARCHIVE"]
        return out
    h1=report["h1DisagreementsAcrossSnapshots"]
    h4=report["h4DisagreementsAcrossSnapshots"]
    reasons=[]
    if missed: reasons.append("MISSING_OBSERVATION_SLOTS")
    if failed: reasons.append("HTTP_FAILURE_SAMPLES")
    if report["providerStaleSamples"]: reasons.append("PROVIDER_STALE_QUOTE_SAMPLES")
    if h1 or h4 or (modern and cats["OHLC_PRICE_DISAGREEMENT"]):
        reasons.append("SOURCE_OHLC_PRICE_DISAGREEMENT")
    if ((modern and cats["UNCLASSIFIED_M15_COVERAGE_GAP"]) or
        report["crossFrameUnverifiedSamples"] or
        report["h1UnclassifiedPartialAggregatesAcrossSnapshots"] or
        report["h4UnclassifiedPartialAggregatesAcrossSnapshots"]):
        reasons.append("UNCLASSIFIED_M15_H1_H4_COVERAGE_GAPS")
    if modern and (cats["OTHER_SOURCE_SHAPE_FAILURE"] or cats["UNAVAILABLE"]):
        reasons.append("SOURCE_GEOMETRY_OR_AUDIT_UNAVAILABLE")
    if legacy and report["auditShapePassedSamples"]<ok:
        reasons.append("LEGACY_FAILED_GEOMETRY_CLASS_NOT_AVAILABLE")
    if not report["h1FullyCoveredComparedAcrossSnapshots"] or not report["h4FullyCoveredComparedAcrossSnapshots"]:
        reasons.append("NO_FULLY_COVERED_H1_H4_OHLC_COMPARISONS")
    if not reasons: reasons.append("ONLY_SAMPLED_SOURCE_GEOMETRY_VERIFIED")
    reasons.extend(["UPSTREAM_MT5_BROKER_RIGHTS_NOT_WARRANTED",
                    "BROKER_SESSION_CALENDAR_NOT_INDEPENDENTLY_VERIFIED",
                    "HISTORICAL_BID_ASK_AND_TRADING_COSTS_NOT_VERIFIED",
                    "GC_DXY_NEWS_YIELDS_ORDERFLOW_NOT_LIVE_VERIFIED",
                    "FORWARD_PROFITABILITY_NOT_TESTED"])
    out.update(status="REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE",
               reasonCodes=reasons,
               reportSchema="LEGACY_989699CD_NO_FAILURE_CLASS" if legacy else "EXTENDED_TYPED_FAILURE_CLASSES",
               samplesObserved=n,missedSlots=missed,
               httpOkSamples=ok,h1OHLCDisagreements=h1,h4OHLCDisagreements=h4,
               unclassifiedCoverageSamples=report["crossFrameUnverifiedSamples"])
    return out

def main():
    # Accept a final JSON report via stdin only; not a log stream containing
    # raw upstream payloads or secrets. The output contains no prices.
    try:
        raw=sys.stdin.read(48000)
        if len(raw)>=48000: raise ValueError("INPUT_TOO_LARGE")
        parsed=json.loads(raw)
        result=verdict(parsed)
    except (ValueError,TypeError):
        result={**SAFE,"status":"BLOCKED",
                "reasonCodes":["FINAL_REPORT_UNREADABLE"]}
    print(json.dumps(result,sort_keys=True,allow_nan=False))

if __name__=="__main__":
    main()
