"""Exactly one public, credential-free BiQuote XAUUSD HTTP preflight.

Read-only and diagnostic only. Never polls, retries, connects a trading account,
starts a websocket, issues an order or invokes an engine. An EXPLICIT
in-process private sink can archive an already fetched sample without extra GETs;
by default no data is written, and no full source OHLC envelopes are returned.
A green HTTP probe cannot establish underlying MT5 broker data rights.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.request

from biquote_offline_source_audit import audit_biquote_sample
from biquote_overlap_evidence import diagnose_biquote_overlap
from biquote_session_gap_audit import audit_gap_times

UTC = dt.timezone.utc
ENDPOINTS = (
    ("quote", "https://biquote.io/api/XAUUSD?allowStale=false"),
    ("M15", "https://biquote.io/api/XAUUSD/ohlc?interval=15m&limit=200"),
    ("H1", "https://biquote.io/api/XAUUSD/ohlc?interval=1h&limit=180"),
    ("H4", "https://biquote.io/api/XAUUSD/ohlc?interval=4h&limit=180"),
)
MAX_RESPONSE_BYTES = 1_000_000

# Only fixed status codes cross the diagnostic boundary. No vendor payloads,
# provider exception text, URL paths, bid/ask, candles or client credentials.
DIAGNOSTIC_CODES = (
    "OK", "HTTP_429", "HTTP_NON_200", "NO_HTTP_RESPONSE",
    "INVALID_JSON_OR_ENVELOPE", "MISSING_REQUIRED_ENVELOPE_FIELD",
)
def classify_http_record(record):
    if not isinstance(record,dict):
        return "NO_HTTP_RESPONSE"
    status=record.get("httpStatus")
    if status == 429:
        return "HTTP_429"
    if type(status) is not int:
        return "NO_HTTP_RESPONSE"
    if status != 200:
        return "HTTP_NON_200"
    if record.get("jsonObject") is not True:
        return "INVALID_JSON_OR_ENVELOPE"
    if record.get("dataPresent") is not True:
        return "MISSING_REQUIRED_ENVELOPE_FIELD"
    return "OK"


def one_shot_probe(opener=None, clock=None, *, private_snapshot_sink=None):
    """Open each fixed public URL once; no credentials, retries or writes.

    Inject opener and clock for offline deterministic regressions. Return a
    sanitized report, not raw quotes/candles, and retain no market history.
    Only a separately approved private sink receives an in-memory original
    sample; its result is reduced to non-price metadata. No additional GETs.
    """
    opener = urllib.request.urlopen if opener is None else opener
    clock = (lambda: dt.datetime.now(UTC)) if clock is None else clock
    received = {}
    metadata = []
    for label, url in ENDPOINTS:
        record = {"endpoint": label, "httpStatus": None,
                  "jsonObject": False, "dataPresent": False}
        request = urllib.request.Request(
            url, headers={"Accept": "application/json",
                          "User-Agent": "GoldPrecisionPro-ReadOnly-OneShot/1.0"},
            method="GET")
        try:
            with opener(request, timeout=12) as response:
                record["httpStatus"] = response.status
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("RESPONSE_SIZE_LIMIT")
            if record["httpStatus"] != 200:
                raise ValueError("HTTP_NOT_OK")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("RESPONSE_JSON_OBJECT_REQUIRED")
            record["jsonObject"] = True
            record["dataPresent"] = ("symbol" in data if label == "quote" else "bars" in data)
            received[label] = data
            if label == "quote":
                record["quoteTimeUTC"] = data.get("timestamp")
                record["marketState"] = data.get("marketState")
                record["providerStale"] = data.get("stale")
                record["bid"] = data.get("bid")
                record["ask"] = data.get("ask")
            else:
                record["barCountReturned"] = len(data.get("bars", [])) if isinstance(data.get("bars"), list) else None
                record["reportedInterval"] = data.get("interval")
        except urllib.error.HTTPError as error:
            record["httpStatus"] = error.code
            record["blocker"] = "PUBLIC_HTTP_REJECTED"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                json.JSONDecodeError) as error:
            record["blocker"] = "PUBLIC_HTTP_OR_JSON_FAILURE"
            record["failureClass"] = type(error).__name__
        metadata.append(record)

    now = clock()
    result = {
        "status": "WAIT_BIQUOTE_PUBLIC_ONE_SHOT",
        "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
        "researchEligible": False, "providerConnected24x5": False,
        "requestCountAttempted": len(ENDPOINTS),
        "retryCount": 0, "credentialsUsed": False,
        "orderEndpointsCalled": False, "subscriptionActivated": False,
        "httpResults": metadata,
        "allHttp200AndValidJson": all(r["httpStatus"] == 200 and r["jsonObject"]
                                     and r["dataPresent"] for r in metadata),
        "marketDataStored": False,
        "blockingReasons": ["NO_INDEPENDENT_UPSTREAM_BROKER_RIGHTS_OR_SESSION_PROOF",
                             "MID_CANDLES_CANNOT_REPLACE_BID_ASK_OR_COMEX_ORDER_FLOW",
                             "NO_TRADING_OR_RESEARCH_ADMISSION"]
    }
    if result["allHttp200AndValidJson"]:
        audit = audit_biquote_sample(
            received["quote"],
            {tf: received[tf] for tf in ("M15", "H1", "H4")}, now=now
        )
        result["dataGeometryConformance"] = (
            "SHAPE_CHECKS_PASSED_BUT_UNLICENSED" if audit["ohlcStructuralChecksPassed"]
            else "SHAPE_CHECKS_FAILED_OR_INCOMPLETE")
        result["overlapEvidence"] = diagnose_biquote_overlap(
            {tf: received[tf] for tf in ("M15", "H1", "H4")}, now=now
        )
        # Gap timings only, no prices, trade hours derived from a GENERAL
        # winter reference, never a claim about the upstream MT5 broker.
        result["sessionGapReferenceOnly"] = audit_gap_times(
            {tf: received[tf] for tf in ("M15", "H1", "H4")}
        )
        # Partial time-grid coverage is not proof of wrong OHLC prices.
        # BOTH still remain blocked as independent trading data.
        problems = audit["blockingReasons"]
        # The full audit may stop at its FIRST M15 coverage gap. The
        # independent read-only overlap pass also checks all other fully
        # covered groups and impossible price bounds in partial groups.
        overlap_groups=result.get("overlapEvidence",{}).get("overlap",{})
        observable_price_contradiction=any(
            overlap_groups.get(tf,{}).get("fullyCoveredOHLCDisagree",0)>0 or
            overlap_groups.get(tf,{}).get("partialObservedOHLCBoundDisagreements",0)>0
            for tf in ("H1","H4"))
        if ("CROSS_TIMEFRAME_OHLC_MISMATCH" in problems or
                observable_price_contradiction):
            result["geometryFailureClass"] = "OHLC_PRICE_DISAGREEMENT"
        elif "PARTIAL_CROSS_TIMEFRAME_COVERAGE" in problems:
            result["geometryFailureClass"] = "UNCLASSIFIED_M15_COVERAGE_GAP"
        elif not audit["ohlcStructuralChecksPassed"]:
            result["geometryFailureClass"] = "OTHER_SOURCE_SHAPE_FAILURE"
        else:
            result["geometryFailureClass"] = "NO_STRUCTURAL_FAILURE"
        if not audit["ohlcStructuralChecksPassed"]:
            result["blockingReasons"].append("CROSS_TIMEFRAME_STRUCTURE_NOT_PROVEN")
        result["structuralAudit"] = {
            "ohlcStructuralChecksPassed": audit["ohlcStructuralChecksPassed"],
            "closedBarCounts": audit["closedBarCounts"],
            "quoteAgeSeconds": audit["quoteAgeSeconds"],
            "blockingReasons": audit["blockingReasons"],
            "candlePriceBasis": audit["candlePriceBasis"],
            "underlyingBrokerRightsWarranted": audit["underlyingBrokerRightsWarranted"]
        }
    else:
        result["blockingReasons"].append("PUBLIC_HTTP_NOT_FULLY_AVAILABLE")
    # Diagnostic-only projection; data already fetched above. Provider
    # 'stale=false' never overrides an independent UTC quote freshness test.
    # H4 partial coverage is not an OHLC price disagreement.
    diag={"mode":"BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY",
          "endpoint":{label:classify_http_record(item)
                      for (label,_),item in zip(ENDPOINTS,metadata)},
          "independentQuoteAgeOver30Seconds":False,
          "independentQuoteAgeInvalid":False,
          "h1InternalM15Gaps":0,"h4InternalM15Gaps":0,
          "h4RetentionEdgesIncomplete":0,
          "h4PartialObservedPriceContradictions":0,
          "h4MissingM15VendorPauseCandidates":0,
          "h4MissingM15OutsideVendorReference":0,
          "h4MissingM15ReferenceUnknown":0,
          "h1CoveredOHLCDisagreements":0,"h4CoveredOHLCDisagreements":0,
          "marketDataExposed":False,"sourceRequestsMade":0,
          "tradingEnabled":False}
    if result["allHttp200AndValidJson"]:
        age=result["structuralAudit"].get("quoteAgeSeconds")
        if type(age) in (int,float) and isinstance(age,(int,float)):
            import math
            if math.isfinite(age) and 0<=age<=86400:
                diag["independentQuoteAgeOver30Seconds"]=age>30
            else:
                diag["independentQuoteAgeInvalid"]=True
        else:
            diag["independentQuoteAgeInvalid"]=True
        overlap=result.get("overlapEvidence",{}).get("overlap",{})
        for tf in ("H1","H4"):
            data=overlap.get(tf,{})
            for field,key in (
                ("internalM15ConstituentGaps","h"+tf[1]+"InternalM15Gaps"),
                ("fullyCoveredOHLCDisagree","h"+tf[1]+"CoveredOHLCDisagreements")):
                count=data.get(field)
                if type(count) is int and 0<=count<=10000:
                    diag[key]=count
        h4=overlap.get("H4",{})
        for source,target in (
            ("partialObservedOHLCBoundDisagreements","h4PartialObservedPriceContradictions"),
            ("partialMissingM15ReferencePauseCandidates","h4MissingM15VendorPauseCandidates"),
            ("partialMissingM15OutsideReferenceTradingTime","h4MissingM15OutsideVendorReference"),
            ("partialMissingM15UnknownSeason","h4MissingM15ReferenceUnknown")):
            count=h4.get(source)
            if type(count) is int and 0<=count<=10000:
                diag[target]=count
        n=h4.get("oldestOrNewestWindowEdgeIncomplete")
        if type(n) is int and 0<=n<=10000:
            diag["h4RetentionEdgesIncomplete"]=n
    result["qualityDiagnostic"]=diag
    # Optional and strictly in-memory: the same four successful public GETs
    # are delivered to an explicitly configured private archive sink.
    # The full OHLC envelopes are never returned from this probe.
    if private_snapshot_sink is not None:
        capture = {"enabled": True, "attempted": False, "saved": False,
                   "newClosedBars": {"M15": 0, "H1": 0, "H4": 0}}
        if result["allHttp200AndValidJson"]:
            capture["attempted"] = True
            try:
                if not callable(private_snapshot_sink):
                    raise TypeError("PRIVATE_SINK_REQUIRED")
                output = private_snapshot_sink(
                    {"source": "BiQuote", "quote": received["quote"],
                     "frames": {tf: received[tf] for tf in ("M15", "H1", "H4")}},
                    now)
                if (not isinstance(output, dict) or output.get("signal") != "WAIT"
                    or output.get("executable") is not False
                    or output.get("rawDataReturnedToCaller") is not False):
                    raise ValueError("PRIVATE_SINK_UNSAFE_RESULT")
                capture["saved"] = output.get("sourceMarketDataPersistedToPrivateVault") is True
                capture["newClosedBars"] = {
                    tf: int(output.get("newClosedBars", {}).get(tf, 0))
                    for tf in ("M15", "H1", "H4")}
            except (ValueError, TypeError, OSError) as error:
                code = str(error)
                capture["blockedReason"] = (code if re.fullmatch(r"[A-Z0-9_]{3,72}", code)
                                            else "PRIVATE_CAPTURE_REJECTED")
            except Exception:
                capture["blockedReason"] = "PRIVATE_CAPTURE_ERROR"
        result["privateArchive"] = capture
        # Legacy public one-shot contract remains false without an opt-in sink.
        result["marketDataStored"] = capture["saved"]
    return result


if __name__ == "__main__":
    report = one_shot_probe()
    print("BIQUOTE_ONE_SHOT_PUBLIC_READONLY " + json.dumps(report, sort_keys=True,
                                                         separators=(",", ":")))
    # A partial or blocked public API is a failed data probe, not a passed feed.
    raise SystemExit(0 if report["allHttp200AndValidJson"] else 2)
