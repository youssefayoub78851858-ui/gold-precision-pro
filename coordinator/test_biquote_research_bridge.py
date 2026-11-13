"""Synthetic-only regression: no BiQuote connection or paper trades."""
import socket
import subprocess
import unittest
from unittest.mock import patch
from biquote_research_bridge import review_biquote_standby
from test_biquote_offline_source_audit import NOW, make_samples

class BiQuoteStandbyBridgeTests(unittest.TestCase):
    def review(self, quote=None, feeds=None):
        original_quote, original_feeds = make_samples()
        return review_biquote_standby(
            original_quote if quote is None else quote,
            original_feeds if feeds is None else feeds, as_of=NOW)

    def blocked(self, r):
        self.assertEqual(r["signal"], "WAIT")
        self.assertFalse(r["executable"])
        self.assertFalse(r["researchEligible"])
        self.assertFalse(r["providerConnected"])
        self.assertEqual(r["sourceRequestsMade"], 0)
        self.assertEqual(r["orderRequestsMade"], 0)
        self.assertEqual(r["engineStatus"], "NOT_INVOKED_SOURCE_GATE_CLOSED")
        self.assertEqual(r["researchIntakeStatus"], "BLOCKED")
        self.assertIn("SOURCE_RIGHTS_OR_ENABLEMENT_NOT_VERIFIED",
                      r["researchIntakeReasons"])
        self.assertFalse(r["paperAdmission"]["paperOrdersAllowed"])
        self.assertFalse(r["paperAdmission"]["ledgerCreatedByGate"])

    def test_valid_geometry_is_not_licence_or_paper_permission(self):
        r = self.review()
        self.blocked(r)
        self.assertTrue(r["sourceAudit"]["ohlcStructuralChecksPassed"])
        self.assertEqual(r["sourceAudit"]["closedBarCounts"],
                         {"M15": 800, "H1": 200, "H4": 50})
        self.assertTrue(any("expected session schedule missing" in reason
                            for reason in r["researchIntakeReasons"]))

    def test_fake_approval_fields_never_authorize(self):
        quote, feeds = make_samples()
        quote.update({"rightsVerified": True, "sourceApproved": True,
                      "paperOrdersAllowed": True, "executable": True})
        for frame in feeds.values():
            frame["expectedOpenTimes"] = ["2026-11-01T00:00:00Z"]
        self.blocked(self.review(quote, feeds))

    def test_open_bar_does_not_make_paper_eligible(self):
        quote, feeds = make_samples()
        feeds["M15"]["bars"][0]["isOpen"] = True
        r = self.review(quote, feeds)
        self.blocked(r)
        self.assertEqual(r["sourceAudit"]["closedBarCounts"]["M15"], 799)

    def test_crossed_quote_and_mismatched_h4_are_blocked(self):
        quote, feeds = make_samples()
        quote["ask"] = quote["bid"] - 1
        feeds["H4"]["bars"][0]["close"] += 1
        feeds["H4"]["bars"][0]["high"] += 1
        r = self.review(quote, feeds)
        self.blocked(r)
        self.assertFalse(r["sourceAudit"]["ohlcStructuralChecksPassed"])
        self.assertIn("INVALID_OR_CROSSED_BID_ASK",
                      r["sourceAudit"]["blockingReasons"])

    def test_no_network_or_research_engine_invocation(self):
        quote, feeds = make_samples()
        with patch.object(socket, "socket", side_effect=AssertionError("NETWORK")), \
             patch.object(subprocess, "run", side_effect=AssertionError("ENGINE")):
            self.blocked(self.review(quote, feeds))

    def test_missing_feeds_fail_closed(self):
        r = self.review(feeds={})
        self.blocked(r)
        self.assertIn("THREE_FRAMES_REQUIRED", r["sourceAudit"]["blockingReasons"])

if __name__ == "__main__":
    unittest.main()
