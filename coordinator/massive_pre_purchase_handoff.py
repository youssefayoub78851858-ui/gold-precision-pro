"""Massive C:XAUUSD pre-purchase, offline synthetic adapter-to-intake drill.

Connects the already implemented fictional REST BBO quote adapter to the
*actual* existing XAU/USD research pipeline input boundary. No REST/WS,
secrets, keys, payments, prices in output, Render writes, trading or paper.
A synthetic simulation can prove software compatibility only; even 50
complete H4 groups are NOT evidence of paid API entitlement, quote
density, source rights, real-time feed access or strategy profitability.
"""
from __future__ import annotations

import datetime as dt

from massive_bbo_history_adapter import review_synthetic_massive_bbo
from xauusd_feed_gate import SourcePolicy, intake_payload
from xauusd_research_pipeline import run_research_pipeline

MODE = "MASSIVE_PREPURCHASE_SYNTHETIC_RESEARCH_HANDOFF_V1"
FAMILY = {"M15": "15min", "H1": "1h", "H4": "4h"}
FIELDS = ("openTime", "open", "high", "low", "close")


def _blocked(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "mockQuoteCount": 0, "mockClosedFrameCounts": {k: 0 for k in FAMILY},
        "minimum50H4SyntheticGeometry": False,
        "historicalAndRealtimeBBOEntitlementVerified": False,
        "all2026HistoricalWindowsVerified": False,
        "independentSessionCalendarVerified": False,
        "askSeriesBrokerParityVerified": False,
        "receiptTimeIndependentlyAttested": False,
        "cloudDataRightsConfirmed": False,
        "actualMassiveFeedConnected": False,
        "realMarketPricesUsed": False,
        "readOnlyEngineInvoked": False,
        "paperJournalOpened": False,
        "purchaseRecommended": False,
        "readyForTradingSignals": False,
        "missingVerifiedProviderEvidence": [
            "C:XAUUSD_2026_AUG_SEP_OCT_BBO_COVERAGE",
            "EXACT_PLAN_HISTORICAL_AND_WEBSOCKET_ENTITLEMENT",
            "PRIVATE_RENDER_CLOUD_RIGHTS_AND_DATA_RETENTION",
            "INDEPENDENT_GOLD_SESSION_AND_BROKER_PRICE_BASIS",
            "REAL_FORWARD_PAPER_VALIDATION_AFTER_COSTS",
        ],
        "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "providerRequestsMade": 0, "brokerOrdersSent": 0, "paymentsMade": 0,
    }


def inspect_mock_massive_handoff(mock_quotes, *, as_of_utc):
    """Return safe counts; never expose synthetic quote values or approve use."""
    if not isinstance(mock_quotes, dict):
        return _blocked("SYNTHETIC_BBO_FIXTURE_REQUIRED")
    try:
        normalized = review_synthetic_massive_bbo(
            mock_quotes, as_of_utc=as_of_utc)
        # Synthetic "receivedUTC" is a fixture timestamp ONLY; it cannot
        # be backfilled into real historical first-seen evidence.
        asof = dt.datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
        if asof.tzinfo is None or asof.utcoffset() != dt.timedelta(0):
            return _blocked("INDEPENDENT_UTC_CLOCK_REQUIRED")
        frame_data = {}
        for tf, interval in FAMILY.items():
            bars = normalized["bidFrames"][tf]
            if not bars:
                return _blocked("MISSING_SYNTHETIC_CLOSED_" + tf)
            frame_data[interval] = {
                "candles": [
                    {key: row[key] for key in FIELDS}
                    for row in bars
                ],
                "expectedOpenTimes": [row["openTime"] for row in bars],
            }
        packet = {
            "provider": "MASSIVE_SYNTHETIC_TEST_ONLY",
            "instrument": "XAU/USD",
            "priceBasis": "BID",
            "mode": "synthetic",
            "receivedUTC": as_of_utc,
            "frames": frame_data,
        }
        policy = SourcePolicy(expected_provider="MASSIVE_SYNTHETIC_TEST_ONLY")
        shaped = intake_payload(packet, asof, policy)
        # Actual research pipeline must NOT launch V3/r2 or paper on
        # this mock, even if historical shape contains 50 H4 groups.
        downstream = run_research_pipeline(
            packet, asof, policy, {},
            allow_synthetic_simulation=False
        )
        if (downstream.get("engines") != {
                "v3": "SKIPPED", "ultimateR2": "SKIPPED",
                "diagnostics": "SKIPPED", "paper": "SKIPPED"
            } or downstream.get("signal") != "WAIT" or
                downstream.get("executable") is not False or
                downstream.get("researchEligible") is not False or
                "paperSnapshot" in downstream):
            return _blocked("SYNTHETIC_RESEARCH_QUARANTINE_BREACHED")
        # A caller may not relabel a mock as real and self-assert
        # entitlements, receipts, broker session or licensing.
        renamed = {**packet, "mode": "recorded", "provider": "Massive"}
        untrusted = intake_payload(
            renamed, asof, SourcePolicy(expected_provider="Massive"))
        if (untrusted["status"] != "BLOCKED" or
                untrusted["researchEligible"] is not False):
            return _blocked("UNLICENSED_MOCK_PROMOTED_TO_RESEARCH")
        if shaped["status"] != "SYNTHETIC_TEST_ONLY":
            return _blocked("MASSIVE_MOCK_INTAKE_GEOMETRY_FAILED")
        result = _blocked(
            "PASSING_SYNTHETIC_50_H4_DOES_NOT_PROVE_HISTORICAL_BBO_COVERAGE"
        )
        result.update({
            "status": "MOCK_BBO_TO_RESEARCH_GATE_TESTED_NOT_MARKET_VERIFIED",
            "mockQuoteCount": normalized["quotesValidated"],
            "mockClosedFrameCounts": normalized["completeClosedBarCounts"],
            "minimum50H4SyntheticGeometry":
                normalized["minimumClosed50H4MetBySyntheticGeometry"],
            "mockUnclassifiedM15Discontinuities":
                normalized["unverifiedM15Discontinuities"],
            "mockDiscardedIncompleteM15":
                normalized["incompleteM15Discarded"],
            "researchIntakeRecognizedSyntheticOnly": True,
        })
        return result
    except (OSError, TypeError, KeyError, ValueError, AttributeError,
            OverflowError):
        return _blocked("INVALID_OR_UNTRUSTED_MASSIVE_MOCK_BBO")


if __name__ == "__main__":
    raise SystemExit("NO_PROVIDER_CALLS_OR_PAYMENT_OFFLINE_ONLY")
