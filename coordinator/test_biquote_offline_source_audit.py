"""Synthetic-only regression tests; BiQuote/network never contacted."""
import copy
import datetime as dt
import socket
import unittest
from unittest.mock import patch

from biquote_offline_source_audit import audit_biquote_sample

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 10, 12, tzinfo=UTC)
START = dt.datetime(2026, 11, 1, tzinfo=UTC)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def candle(t, o, h, l, c):
    return {"openTime": iso(t), "open": o, "high": h, "low": l,
            "close": c, "volume": 0, "tickVolume": 12, "isOpen": False}


def make_samples():
    # Artificial regular bars for geometry ONLY, not a market session calendar.
    m15 = []
    for i in range(800):
        o = 3900 + i * 0.01
        m15.append(candle(START + dt.timedelta(minutes=i * 15),
                          o, o + 0.4, o - 0.2, o + 0.1))
    h1, h4 = [], []
    for factor, target in ((4, h1), (16, h4)):
        for i in range(0, len(m15), factor):
            group = m15[i:i+factor]
            target.append(candle(
                START + dt.timedelta(minutes=i*15),
                group[0]["open"],
                max(x["high"] for x in group),
                min(x["low"] for x in group),
                group[-1]["close"]))
    feeds = {
        "M15": {"symbol": "XAUUSD", "interval": "15m", "bars": m15[::-1]},
        "H1": {"symbol": "XAUUSD", "interval": "1h", "bars": h1[::-1]},
        "H4": {"symbol": "XAUUSD", "interval": "4h", "bars": h4[::-1]},
    }
    quote = {"symbol": "XAUUSD", "bid": 3907.1, "ask": 3907.3,
             "timestamp": iso(NOW - dt.timedelta(seconds=1)),
             "stale": False, "source": "MOCK_SYNTHETIC_ONLY"}
    return quote, feeds


class BiquoteOfflineAuditTests(unittest.TestCase):
    def run_audit(self, quote=None, feeds=None):
        original_quote, original_feeds = make_samples()
        return audit_biquote_sample(
            original_quote if quote is None else quote,
            original_feeds if feeds is None else feeds, now=NOW)

    def assert_safe(self, r):
        self.assertEqual(r["signal"], "WAIT")
        self.assertFalse(r["researchEligible"])
        self.assertFalse(r["executable"])
        self.assertFalse(r["paperOrdersAllowed"])
        self.assertEqual(r["sourceRequestsMade"], 0)
        self.assertEqual(r["paymentsMade"], 0)
        self.assertFalse(r["independentSourceLicenceVerified"])
        self.assertFalse(r["mayMergeWithBrokerBidAskOrComexOrderFlow"])
        self.assertIn("BIQUOTE_UPSTREAM_MT5_DATA_RIGHTS_FOR_PRIVATE_RENDER_NOT_CONFIRMED",
                      r["blockingReasons"])

    def test_800_mathematically_consistent_m15_still_cannot_authorize_signal(self):
        r = self.run_audit()
        self.assert_safe(r)
        self.assertTrue(r["ohlcStructuralChecksPassed"])
        self.assertEqual(r["closedBarCounts"], {"M15": 800, "H1": 200, "H4": 50})
        self.assertEqual(r["quoteAgeSeconds"], 1.0)

    def test_cross_frame_mismatch_quarantined(self):
        q, feeds = make_samples()
        feeds["H4"]["bars"][0]["close"] += 1
        feeds["H4"]["bars"][0]["high"] += 1
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertFalse(r["ohlcStructuralChecksPassed"])
        self.assertIn("CROSS_TIMEFRAME_OHLC_MISMATCH", r["blockingReasons"])

    def test_open_bar_never_counted_or_trusted(self):
        q, feeds = make_samples()
        feeds["M15"]["bars"][0]["isOpen"] = True
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertEqual(r["closedBarCounts"]["M15"], 799)
        self.assertFalse(r["ohlcStructuralChecksPassed"])
        self.assertIn("PARTIAL_CROSS_TIMEFRAME_COVERAGE", r["blockingReasons"])

    def test_open_bar_in_middle_rejected(self):
        q, feeds = make_samples()
        feeds["M15"]["bars"][2]["isOpen"] = True
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertIn("OPEN_CANDLE_NOT_FIRST", r["blockingReasons"])

    def test_stale_quote_rejected_even_if_vendor_claims_fresh(self):
        q, feeds = make_samples()
        q["timestamp"] = iso(NOW - dt.timedelta(minutes=2))
        q["quoteAgeSeconds"] = 1
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertIn("INDEPENDENT_QUOTE_CLOCK_FRESHNESS_FAILED", r["blockingReasons"])

    def test_crossed_quote_and_boolean_prices_rejected(self):
        q, feeds = make_samples()
        q["bid"] = q["ask"] + 1
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertIn("INVALID_OR_CROSSED_BID_ASK", r["blockingReasons"])
        q["bid"] = True
        r = self.run_audit(q, feeds)
        self.assertIn("INVALID_OR_CROSSED_BID_ASK", r["blockingReasons"])

    def test_malformed_ohlc_and_time_rejected(self):
        q, feeds = make_samples()
        feeds["M15"]["bars"][0]["high"] = 1
        r = self.run_audit(q, feeds)
        self.assert_safe(r)
        self.assertIn("INVALID_OHLC_EXTREMA", r["blockingReasons"])
        q, feeds = make_samples()
        feeds["H1"]["bars"][0]["openTime"] = "2026-11-09T07:00:00+02:00"
        r = self.run_audit(q, feeds)
        self.assertIn("UTC_OFFSET_REQUIRED", r["blockingReasons"])

    def test_no_network_or_secret_access(self):
        q, feeds = make_samples()
        with patch.object(socket, "socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            r = self.run_audit(q, feeds)
        self.assert_safe(r)


if __name__ == "__main__":
    unittest.main()
