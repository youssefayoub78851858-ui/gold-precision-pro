"""Offline multi-source completeness audit for Gold Precision Pro Ultimate.

Composes existing, isolated SYNTHETIC fixture validators for Massive XAUUSD
historical BBO and Databento GC MBO/MBP-10. Lists missing DXY, daily yield,
calendar, headlines and cost evidence. It NEVER authorizes live prices,
strategy research, paper orders or broker execution.

No networking, API clients, credentials, environment inspection or payments.
Inputs claiming source rights or 'live' are rejected at the fixture boundary.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re

from databento_gc_book_preflight import validate_rows
from massive_bbo_history_adapter import review_synthetic_massive_bbo
from recorded_utils import ns

LAYERS = (
    ("XAUUSD_BBO", "Massive", "HISTORICAL_BID_ASK_AND_LIVE_QUOTE_PARITY"),
    ("GC_TRADES", "Databento", "EXCHANGE_GC_MBO_AND_AGGRESSOR_TRADE_TAPE"),
    ("GC_DEPTH", "Databento", "GC_MBP10_OR_MBO_FULL_DEPTH"),
    ("DXY", "ICE_OR_LICENSED_INDEX", "VERIFIED_INTRADAY_DXY"),
    ("US02Y", "OFFICIAL_FED_TREASURY", "DAILY_CONTEXT_ONLY"),
    ("US10Y", "OFFICIAL_FED_TREASURY", "DAILY_CONTEXT_ONLY"),
    ("CALENDAR", "INDEPENDENT_SCHEDULE", "COMPLETE_USD_CALENDAR_WITH_ACTUAL_AND_CONSENSUS"),
    ("HEADLINES", "LICENSED_NEWS", "TIMESTAMPED_USD_GOLD_WORLD_NEWS"),
    ("RISK_COSTS", "BROKER_AND_STRATEGY", "SPREAD_SLIPPAGE_COMMISSION_AND_REALISTIC_FILLS"),
)
GC_CONTRACT = re.compile(r"^GC[FGHJKMNQUVXZ][0-9]{1,4}$")


def _stamp(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("EXPLICIT_ASOF_UTC_REQUIRED")
    try:
        stamp = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("EXPLICIT_ASOF_UTC_REQUIRED") from error
    if stamp.utcoffset() != dt.timedelta(0):
        raise ValueError("EXPLICIT_ASOF_UTC_REQUIRED")
    return stamp.astimezone(dt.timezone.utc)


def _gc_fixture(document, expected_schema, as_of_utc):
    if document is None:
        return None
    if not isinstance(document, dict) or set(document) != {"dataOrigin", "schema", "contract", "rows"}:
        raise ValueError("EXACT_SYNTHETIC_GC_FIXTURE_REQUIRED")
    if document["dataOrigin"] != "SYNTHETIC_TEST_ONLY":
        raise ValueError("LIVE_OR_RECORDED_GC_NOT_AUTHORIZED")
    if document["schema"] != expected_schema or not isinstance(document["contract"], str) or not GC_CONTRACT.fullmatch(document["contract"]):
        raise ValueError("GC_CONTRACT_OR_SCHEMA_MISMATCH")
    result = validate_rows(expected_schema, document["rows"], as_of_utc)
    latest = ns(document["rows"][-1]["ts_event"])  # exactly the GC fixture's event timestamp
    return {"kind": "SYNTHETIC_STRUCTURE_ONLY",
            "contract": document["contract"], "sampleRows": result["rowsValidated"],
            "lastEventUTC": dt.datetime.fromtimestamp(latest / 1e9, tz=dt.timezone.utc)
                .isoformat().replace("+00:00", "Z")}


def assess_offline_stack(*, as_of_utc, xau_fixture=None, gc_mbo_fixture=None,
                         gc_mbp10_fixture=None):
    """Compute only schema coverage and unresolved gates. Always WAIT.

    An actual evidence pipeline must separately attest licensed private rights,
    source-native observation/availability times and session/contract mapping.
    Caller-controlled verification flags cannot mark a source operational.
    """
    clock = _stamp(as_of_utc)
    layers = {
        name: {"providerCandidate": candidate, "requiredEvidence": requirement,
               "liveReady": False, "researchAdmitted": False,
               "status": "NOT_CONNECTED", "reason": "REAL_SOURCE_ENTITLEMENT_AND_EVIDENCE_NOT_VERIFIED"}
        for name, candidate, requirement in LAYERS
    }
    for name in ("US02Y", "US10Y"):
        layers[name]["status"] = "FREE_DAILY_REFERENCE_CANDIDATE"
        layers[name]["reason"] = "DAILY_OFFICIAL_REFERENCE_NOT_INTRADAY_EVIDENCE"
    xau = mbo = depth = None
    rejected = []

    if xau_fixture is not None:
        try:
            xau = review_synthetic_massive_bbo(xau_fixture, as_of_utc=as_of_utc)
            counts = xau["completeClosedBarCounts"]
            layers["XAUUSD_BBO"].update(
                status="SYNTHETIC_WARMUP_GEOMETRY_ONLY",
                reason="BBO_FIXTURE_IS_NOT_LICENSED_MATCHED_LIVE_HISTORY",
                syntheticClosedBars={k: counts[k] for k in ("M15", "H1", "H4")},
                synthetic50H4Reached=xau["minimumClosed50H4MetBySyntheticGeometry"],
                incompleteM15Discarded=xau["incompleteM15Discarded"])
        except (ValueError, TypeError, OverflowError, OSError) as error:
            # Only constant validator codes; never echo incoming quotes.
            layers["XAUUSD_BBO"].update(status="REJECTED_FIXTURE", reason="XAU_FIXTURE_NOT_ADMISSIBLE")
            rejected.append("XAUUSD_BBO")
    for key, document, schema in (
        ("GC_TRADES", gc_mbo_fixture, "mbo"),
        ("GC_DEPTH", gc_mbp10_fixture, "mbp-10"),
    ):
        if document is not None:
            try:
                parsed = _gc_fixture(document, schema, as_of_utc)
                if key == "GC_TRADES":
                    mbo = parsed
                else:
                    depth = parsed
                layers[key].update(status="SYNTHETIC_SCHEMA_ONLY",
                                   reason="GC_FIXTURE_HAS_NO_VERIFIED_TAPE_CONTINUITY_OR_EXCHANGE_ENTITLEMENT",
                                   sampleRows=parsed["sampleRows"])
            except (ValueError, TypeError, OverflowError, KeyError) as error:
                layers[key].update(status="REJECTED_FIXTURE", reason="GC_FIXTURE_NOT_ADMISSIBLE")
                rejected.append(key)

    # Compare derived observed times only as a non-voting diagnostic.
    overlap = {"status": "NOT_TESTABLE", "maxSkewSeconds": None,
               "noIndependentSessionOrAvailabilityEvidence": True}
    if xau is not None and mbo is not None and depth is not None and xau["midFrames"]["M15"]:
        last_m15 = _stamp(xau["midFrames"]["M15"][-1]["openTime"])
        close = last_m15 + dt.timedelta(minutes=15)
        trades_time = _stamp(mbo["lastEventUTC"])
        depth_time = _stamp(depth["lastEventUTC"])
        skew = int((max(close, trades_time, depth_time) -
                    min(close, trades_time, depth_time)).total_seconds())
        same_contract = mbo["contract"] == depth["contract"]
        fresh = all(dt.timedelta(0) <= clock - t <= dt.timedelta(minutes=5)
                    for t in (close, trades_time, depth_time))
        overlap = {"status": ("SYNTHETIC_CLOCK_ALIGNMENT_ONLY" if
                              same_contract and fresh and skew <= 60 else
                              "BLOCKED_SYNTHETIC_SKEW_OR_CONTRACT"),
                   "maxSkewSeconds": skew, "sameSyntheticGCContract": same_contract,
                   "recentSyntheticClocks": fresh,
                   "noIndependentSessionOrAvailabilityEvidence": True}
        if not same_contract:
            rejected.append("GC_CONTRACT_MISMATCH")

    return {
        "mode": "OFFLINE_MULTISOURCE_CAPABILITY_AUDIT",
        "asOfUTC": as_of_utc, "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "realTradingAuthorized": False, "subscriptionsActivated": False,
        "sourceRequestsMade": 0, "secretReads": 0, "payments": 0,
        "verifiedLiveLayerCount": 0, "requiredLayerCount": len(LAYERS),
        "allLayersLive": False, "completeStackReady": False,
        "diagnosticOnlySyntheticTemporalComparison": overlap,
        "rejectedFixtures": sorted(set(rejected)),
        "layers": layers,
        "remainingExternalRequirements": [
            "XAUUSD_REAL_HISTORICAL_BBO_AND_LIVE_SAME_SOURCE_RIGHTS_AND_SESSION_EVIDENCE",
            "GC_REAL_EXCHANGE_TRADES_MBO_MBP10_LICENSE_AND_TIME_PARITY",
            "DXY_APPROVED_INTRADAY_INDEX_AND_GC_CONTRACT_ROLLOVER",
            "US02Y_US10Y_PUBLICATION_LATENCY_AND_DAILY_ONLY_CLASSIFICATION",
            "USD_CALENDAR_ACTUAL_VS_CONSENSUS_AND_GEOPOLITICAL_NEWS_TIME_COVERAGE",
            "BROKER_BID_ASK_SPREAD_SLIPPAGE_COMMISSIONS_AND_RISK_APPROVAL",
            "PRIVATE_AUTHENTICATED_SINGLE_USER_RENDER_DEPLOYMENT_AND_USER_APPROVAL",
        ],
        "warning": "Passing fixture shape, 50 H4 or synchronized synthetic timestamps never proves real data, licensed research or profitability",
    }


def main():
    parser = argparse.ArgumentParser(description="No-network review of all nine data layer requirements")
    parser.add_argument("--as-of-utc", default="2026-11-15T10:00:00Z")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = assess_offline_stack(as_of_utc=args.as_of_utc)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = pathlib.Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
