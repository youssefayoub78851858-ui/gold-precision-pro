"""Offline Massive 50-H4 mock -> actual XAUUSD intake acceptance.

This is NOT a test of a Massive subscription, licensed quotes or real trades.
"""
import copy
import json
import socket
import unittest
from unittest.mock import patch

from massive_pre_purchase_handoff import inspect_mock_massive_handoff
from test_massive_bbo_history_adapter import payload

ASOF = "2026-11-12T08:01:00Z"


class MassivePrePurchaseHandoffTests(unittest.TestCase):
    def assert_wait(self, out):
        self.assertEqual(out["signal"], "WAIT")
        self.assertFalse(out["executable"])
        self.assertFalse(out["paperOrdersAllowed"])
        self.assertFalse(out["liveOrdersAllowed"])
        self.assertFalse(out["purchaseRecommended"])
        self.assertFalse(out["readyForTradingSignals"])
        self.assertFalse(out["historicalAndRealtimeBBOEntitlementVerified"])
        self.assertFalse(out["all2026HistoricalWindowsVerified"])
        self.assertFalse(out["independentSessionCalendarVerified"])
        self.assertFalse(out["askSeriesBrokerParityVerified"])
        self.assertFalse(out["receiptTimeIndependentlyAttested"])
        self.assertFalse(out["cloudDataRightsConfirmed"])
        self.assertFalse(out["actualMassiveFeedConnected"])
        self.assertFalse(out["realMarketPricesUsed"])
        self.assertFalse(out["readOnlyEngineInvoked"])
        self.assertFalse(out["paperJournalOpened"])
        self.assertEqual(out["providerRequestsMade"], 0)
        self.assertEqual(out["brokerOrdersSent"], 0)
        self.assertEqual(out["paymentsMade"], 0)
        self.assertEqual(len(out["missingVerifiedProviderEvidence"]), 5)
        reported = json.dumps(out)
        for raw in ('"bid_price"', '"ask_price"', '"results"',
                    '"open"', '"high"', '"low"', '"close"',
                    "3900.", "C:XAUUSD", "api_key"):
            self.assertNotIn(raw, reported)

    def test_fifty_mock_h4_reaches_real_source_gate_but_never_engines(self):
        with patch.object(socket, "socket",
                          side_effect=AssertionError("NO_NETWORK")), patch(
                    "xauusd_research_pipeline.subprocess.run",
                    side_effect=AssertionError("NO_ENGINES")):
            out = inspect_mock_massive_handoff(payload(bars=800),
                                                as_of_utc=ASOF)
        self.assert_wait(out)
        self.assertEqual(
            out["status"], "MOCK_BBO_TO_RESEARCH_GATE_TESTED_NOT_MARKET_VERIFIED")
        self.assertEqual(out["mockQuoteCount"], 12000)
        self.assertEqual(out["mockClosedFrameCounts"],
                         {"M15": 800, "H1": 200, "H4": 50})
        self.assertTrue(out["minimum50H4SyntheticGeometry"])
        # The synthetic assumed weekend gap is not independently checked.
        self.assertEqual(out["mockUnclassifiedM15Discontinuities"], 1)
        self.assertEqual(out["mockDiscardedIncompleteM15"], 0)
        self.assertTrue(out["researchIntakeRecognizedSyntheticOnly"])
        self.assertFalse(out["purchaseRecommended"])

    def test_one_missing_quote_drops_h4_warmup_never_backfills(self):
        fixture = payload(bars=800)
        fixture["results"].pop(600 * 15 + 7)
        with patch("xauusd_research_pipeline.subprocess.run",
                   side_effect=AssertionError("NO_ENGINES")):
            out = inspect_mock_massive_handoff(fixture, as_of_utc=ASOF)
        self.assert_wait(out)
        self.assertEqual(out["status"],
                         "MOCK_BBO_TO_RESEARCH_GATE_TESTED_NOT_MARKET_VERIFIED")
        self.assertEqual(out["mockClosedFrameCounts"],
                         {"M15": 799, "H1": 199, "H4": 49})
        self.assertEqual(out["mockDiscardedIncompleteM15"], 1)
        self.assertFalse(out["minimum50H4SyntheticGeometry"])

    def test_stale_mock_batch_does_not_pass_actual_intake(self):
        out = inspect_mock_massive_handoff(payload(bars=800),
                                           as_of_utc="2026-11-13T00:00:00Z")
        self.assert_wait(out)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason"], "MASSIVE_MOCK_INTAKE_GEOMETRY_FAILED")

    def test_forged_provider_rights_and_invalid_market_packets(self):
        for mutate in (
            lambda v: v.update(sourceDataMode="recorded"),
            lambda v: v.update(sourceDataMode="live"),
            lambda v: v.update(ticker="C:EURUSD"),
            lambda v: v.update(cloudDataRightsConfirmed=True),
            lambda v: v["results"][0].update(ask_price=1),
            lambda v: v["results"][0].update(participant_timestamp="0"),
        ):
            with self.subTest(mutate=mutate):
                data = payload(bars=1)
                mutate(data)
                result = inspect_mock_massive_handoff(data, as_of_utc=ASOF)
                self.assert_wait(result)
                self.assertEqual(result["status"], "BLOCKED")

    def test_no_fake_operator_approval_via_environment(self):
        with patch.dict("os.environ", {
            "MASSIVE_CURRENCY_RIGHTS_VERIFIED": "true",
            "GPP_SYNTHETIC_TEST_SIMULATION": "1",
            "MASSIVE_API_KEY": "DO_NOT_USE_OR_READ"
        }), patch("xauusd_research_pipeline.subprocess.run",
                   side_effect=AssertionError("NO_ENGINES")):
            out = inspect_mock_massive_handoff(payload(bars=800), as_of_utc=ASOF)
        self.assert_wait(out)
        self.assertEqual(out["status"],
                         "MOCK_BBO_TO_RESEARCH_GATE_TESTED_NOT_MARKET_VERIFIED")


if __name__ == "__main__":
    unittest.main()
