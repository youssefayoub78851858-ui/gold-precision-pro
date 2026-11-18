"""BiQuote 24h sample failures vs VENDOR-DECLARED break (offline only).

Use only the previously published 24h run and independently retrieved sample
timestamps. Never infer that the upstream MT5 broker calendar, usage rights or
execution history has been independently verified. NEVER promote WAIT.
"""
from __future__ import annotations
import datetime as dt
import json
import re
from biquote_24h_final_verdict import verdict
from biquote_session_gap_audit import reference_window_for_missing_slot

UTC=dt.timezone.utc
FIRST=dt.datetime(2026,11,16,19,45,tzinfo=UTC)
END=FIRST+dt.timedelta(hours=24)
MAX_AGE=30
SAFE={"mode":"BIQUOTE_DECLARED_PAUSE_FAILURE_FORENSICS_OFFLINE_V1",
      "signal":"WAIT","executable":False,"paperOrdersAllowed":False,
      "liveOrdersAllowed":False,"researchEligible":False,
      "providerRequestsMade":0,"archiveWritesMade":0,"brokerOrdersSent":0,
      "brokerSessionCalendarIndependentlyVerified":False,
      "brokerSourceRightsIndependentlyVerified":False,
      "independentQuoteFreshnessFullyProven":False,
      "sourceAdmittedToResearchOrTrades":False,"marketDataExposed":False}
TIMESTAMP=re.compile(r"^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$")

def _utc(t):
    if not isinstance(t,str) or not TIMESTAMP.fullmatch(t):
        raise ValueError("FAILURE_TIMESTAMP_FORMAT_INVALID")
    try:
        value=dt.datetime.fromisoformat(t.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("FAILURE_TIMESTAMP_INVALID")
    if value.utcoffset()!=dt.timedelta(0):
        raise ValueError("FAILURE_TIMESTAMP_NOT_UTC")
    return value

def classify_pause_failures(report, failure_observed_utc):
    """Sanitized independent forensic comparison. Inputs are metadata only.

    Exact original run is enforced by verdict(); failure timestamps must be
    exhaustive and unique. A generic vendor-declared pause is NOT evidence
    of an upstream broker calendar or legitimate missing H4 constituents.
    """
    result={**SAFE,"status":"UNVERIFIED",
            "reasonCodes":["FAILURE_TIMING_EVIDENCE_NOT_COMPLETE"],
            "reviewSamples":0,"httpFailedSamples":None,
            "observedFailureTimesCount":0,
            "vendorReferencePauseFailures":None,
            "vendorReferenceTradingTimeFailures":None,
            "outsideReferenceDateRangeFailures":None,
            "allObservedFailuresInsideVendorReferencePause":False,
            "allOpenMarketQuotesFresh":False,
            "allCrossFrameCandlesComplete":False}
    verified=verdict(report)
    if verified.get("status")!="REVIEW_FINISHED_READONLY_NOT_TRADE_ADMISSIBLE":
        result["reasonCodes"]=["FINISHED_REPORT_NOT_VERIFIED"]
        return result
    failed=verified["httpFailedSamples"]
    result["reviewSamples"]=verified["samplesObserved"]
    result["httpFailedSamples"]=failed
    if (not isinstance(failure_observed_utc,list) or
        len(failure_observed_utc)!=failed or
        len(failure_observed_utc)>720):
        return result
    try:
        slots=[_utc(x) for x in failure_observed_utc]
    except ValueError:
        result["reasonCodes"]=["FAILURE_TIMING_METADATA_INVALID"]
        return result
    if len(set(slots))!=len(slots) or slots!=sorted(slots):
        result["reasonCodes"]=["FAILURE_TIMING_NOT_UNIQUE_OR_SORTED"]
        return result
    if any(not FIRST<=stamp<END for stamp in slots):
        result["reasonCodes"]=["FAILURE_TIME_OUTSIDE_ORIGINAL_REVIEW"]
        return result
    # The old worker ran on a 2-minute cadence, a few seconds after
    # its nominal minute. Reject timestamps that contradict it.
    if any((stamp.minute%2)!=1 or stamp.second>15 for stamp in slots):
        result["reasonCodes"]=["FAILURE_TIMING_NOT_ON_OBSERVER_CADENCE"]
        return result
    pause=trading=unknown=0
    for stamp in slots:
        # Classify the 15-min candle containing the failed 2-min sample
        # instead of mistakenly asking whether the NEXT 15-min candle
        # also fits in the pause (would reject 22:59 despite being closed).
        slot=stamp.replace(minute=(stamp.minute//15)*15,second=0,microsecond=0)
        test=reference_window_for_missing_slot(slot,900)
        if test is True:pause+=1
        elif test is False:trading+=1
        else:unknown+=1
    result.update(
        observedFailureTimesCount=len(slots),
        vendorReferencePauseFailures=pause,
        vendorReferenceTradingTimeFailures=trading,
        outsideReferenceDateRangeFailures=unknown,
        allObservedFailuresInsideVendorReferencePause=(
            failed>0 and pause==failed and
            verified.get("missedSlots")==0),
        # This is an explanation of HTTP failures, NOT a passing feed.
        status="VENDOR_PAUSE_ONLY_CANDIDATE" if
            failed>0 and pause==failed and verified.get("missedSlots")==0
            else "OTHER_OR_UNEXPLAINED_FAILURES",
        reasonCodes=(
            ["VENDOR_PAUSE_EXPLAINS_HTTP_FAILURE_TIMING_ONLY",
             "UPSTREAM_BROKER_CALENDAR_UNVERIFIED",
             "HTTP_RELIABILITY_OVER_MARKET_OPEN_UNPROVEN",
             "SOURCE_GEOMETRY_STILL_UNQUALIFIED",
             "INDEPENDENT_QUOTE_AGE_MAXIMUM_EXCEEDED_POLICY"]
            if failed>0 and pause==failed and verified.get("missedSlots")==0
            else ["UNEXPLAINED_FAILURE_TIMING_OR_MISSED_SAMPLES",
                  "UPSTREAM_BROKER_CALENDAR_UNVERIFIED"])
    )
    return result

if __name__=="__main__":
    # CLI intentionally doesn't consume untrusted upstream data, files or
    # credentials, and never automatically queries GitHub/Render/market.
    # Full forensic classification is exercised via unit tests only.
    print(json.dumps({**SAFE,"status":"NO_OBSERVATIONS_SUPPLIED",
        "reasonCodes":["PRIVATE_OBSERVER_FAILURE_TIMES_NOT_SUPPLIED"]},
        sort_keys=True,allow_nan=False))
