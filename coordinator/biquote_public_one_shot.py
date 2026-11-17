"""Exactly one public, credential-free BiQuote XAUUSD HTTP preflight.

Read-only and diagnostic only. Never poll, retry, connect a trading account,
write market-data files, start a websocket, issue an order or invoke an engine.
A green HTTP probe cannot establish underlying MT5 broker data rights.
"""
from __future__ import annotations

import datetime as dt
import json
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


def one_shot_probe(opener=None, clock=None):
    """Open each fixed public URL once; no credentials, retries or writes.

    Inject opener and clock for offline deterministic regressions. Return a
    sanitized report, not raw quotes/candles, and retain no market history.
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
    return result


if __name__ == "__main__":
    report = one_shot_probe()
    print("BIQUOTE_ONE_SHOT_PUBLIC_READONLY " + json.dumps(report, sort_keys=True,
                                                         separators=(",", ":")))
    # A partial or blocked public API is a failed data probe, not a passed feed.
    raise SystemExit(0 if report["allHttp200AndValidJson"] else 2)
