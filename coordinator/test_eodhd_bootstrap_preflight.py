"""Offline bootstrap checks; no vendor contact, quote/secret, or trading."""
import unittest
from unittest.mock import patch

from eodhd_bootstrap_preflight import bootstrap_plan


class BootstrapChecks(unittest.TestCase):
    def assert_wait(self, report):
        self.assertEqual(report["signal"], "WAIT")
        self.assertFalse(report["executable"])
        self.assertFalse(report["readyForTrading"])
        self.assertFalse(report["historyReadyForResearch"])
        self.assertFalse(report["readyForPaper"])
        self.assertEqual(report["sourceRequestsMade"], 0)
        self.assertEqual(report["payments"], 0)
        self.assertEqual(report["secretReads"], 0)
        self.assertFalse(report["sourceCompatibility"]["mayMergeHistoricalAndStreamBars"])

    def test_no_history_explicit_minimum(self):
        result = bootstrap_plan()
        self.assert_wait(result)
        self.assertEqual(result["minimumClosedBars"], {"M15": 50, "H1": 50, "H4": 50})
        self.assertEqual(result["missingToMinimum"], {"M15": 50, "H1": 50, "H4": 50})
        self.assertEqual(result["historyMath"]["minimumClosedM15For50CompleteH4"], 800)
        self.assertEqual(result["historyMath"]["minimumContinuousHoursAtFullMarketCoverage"], 200)
        self.assertIn("CLOSED_BAR_WARMUP_COUNTS_BELOW_MINIMUM", result["blockingReasons"])
        self.assertFalse(result["historyMath"]["800M15SufficientWithoutAlignedCompleteGroups"])

    def test_50_h4_counts_are_not_license_or_session_proof(self):
        for counts in (
            {"M15": 800, "H1": 200, "H4": 50},
            {"M15": 2048, "H1": 512, "H4": 128},
        ):
            report = bootstrap_plan(counts)
            self.assert_wait(report)
            self.assertTrue(report["countMinimumsMet"])
            self.assertEqual(report["missingToMinimum"], {"M15": 0, "H1": 0, "H4": 0})
            self.assertIn("HISTORICAL_FOREX_OHLCV_VS_WEBSOCKET_BID_ASK_EQUIVALENCE_UNVERIFIED",
                          report["blockingReasons"])
            self.assertFalse(report["sourceCompatibility"]["licenseAllowsCloudUseVerified"])

    def test_long_m15_archive_cannot_replace_h4(self):
        r = bootstrap_plan({"M15": 1000, "H1": 250, "H4": 49})
        self.assert_wait(r)
        self.assertFalse(r["countMinimumsMet"])
        self.assertEqual(r["missingToMinimum"]["H4"], 1)
        self.assertNotIn("LESS_THAN_800_CLOSED_M15_SLOTS_FOR_50_H4", r["blockingReasons"])

    def test_bad_count_or_forged_extra_flags_rejected(self):
        for counts in ({"M15": 50, "H1": 50}, {"M15": True, "H1": 50, "H4": 50},
                       {"M15": 0, "H1": -1, "H4": 0},
                       {"M15": 800.0, "H1": 200, "H4": 50},
                       {"M15": 800, "H1": 200, "H4": 50, "licensed": True}):
            with self.subTest(counts=counts):
                with self.assertRaises(ValueError):
                    bootstrap_plan(counts)

    def test_no_network_even_with_complete_counts(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = bootstrap_plan({"M15": 832, "H1": 208, "H4": 52})
        self.assert_wait(result)
        self.assertNotIn("Bearer ", repr(result))
        self.assertNotIn("api_token=", repr(result))


if __name__ == "__main__":
    unittest.main()
