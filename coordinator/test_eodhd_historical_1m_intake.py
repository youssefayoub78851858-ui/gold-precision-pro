"""Synthetic offline 1m XAUUSD history geometry and quarantine tests."""
import datetime as dt
import unittest
from unittest.mock import patch

from eodhd_historical_1m_intake import review_normalized_eodhd_history

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 2, 0, 0, tzinfo=UTC)
NOW = START + dt.timedelta(days=20)


def candidate(count=12000, *, first=START):
    bars = []
    for i in range(count):
        stamp = first + dt.timedelta(minutes=i)
        bars.append({
            "openTime": stamp.isoformat().replace("+00:00", "Z"),
            "open": 4000.0, "high": 4001.0, "low": 3999.0, "close": 4000.2,
        })
    return {"provider": "EODHD", "symbol": "XAUUSD.FOREX", "interval": "1m",
            "candles": bars}


def audit(document):
    return review_normalized_eodhd_history(document, as_of=NOW)


class HistoricalOneMinuteQuarantine(unittest.TestCase):
    def assert_quarantine(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["readyForPaper"])
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["mayMergeWithLiveBidAsk"])
        self.assertEqual(result["priceBasis"], "UNVERIFIED")
        self.assertFalse(result["marketClosureClassificationVerified"])
        self.assertEqual(result["payments"], 0)
        self.assertEqual(result["sourceRequestsMade"], 0)

    def test_50_complete_h4_is_only_geometric_warmup(self):
        result = audit(candidate(12000))
        self.assert_quarantine(result)
        self.assertEqual(result["completeClosedBarCounts"], {
            "M15": 800, "H1": 200, "H4": 50
        })
        self.assertEqual(result["missingCompleteBarsToMinimum"], {
            "M15": 0, "H1": 0, "H4": 0
        })
        self.assertIn("HISTORICAL_PRICE_BASIS_AND_STREAM_BID_ASK_PARITY_UNVERIFIED",
                      result["blockingReasons"])
        self.assertNotIn("COMPLETE_HISTORICAL_WARMUP_INSUFFICIENT",
                         result["blockingReasons"])

    def test_gaps_do_not_create_missing_h4(self):
        doc = candidate(12000)
        del doc["candles"][10]
        result = audit(doc)
        self.assert_quarantine(result)
        self.assertEqual(result["completeClosedBarCounts"]["H4"], 49)
        self.assertEqual(result["completeClosedBarCounts"]["M15"], 799)
        self.assertEqual(result["numberOfUnclassifiedDiscontinuities"], 1)
        self.assertEqual(result["missingOneMinuteSlotsWithoutCalendar"], 1)
        self.assertIn("COMPLETE_HISTORICAL_WARMUP_INSUFFICIENT",
                      result["blockingReasons"])
        self.assertIn("UNCLASSIFIED_HISTORICAL_TIME_GAPS",
                      result["blockingReasons"])

    def test_weekend_like_gap_not_classified_as_closed_session(self):
        doc = candidate(240)
        doc["candles"] += candidate(240, first=START + dt.timedelta(days=3))["candles"]
        result = audit(doc)
        self.assert_quarantine(result)
        self.assertEqual(result["completeClosedBarCounts"]["H4"], 2)
        self.assertEqual(result["numberOfUnclassifiedDiscontinuities"], 1)
        self.assertFalse(result["marketClosureClassificationVerified"])

    def test_partial_boundaries_do_not_count_h4(self):
        doc = candidate(12000, first=START + dt.timedelta(minutes=1))
        result = audit(doc)
        self.assert_quarantine(result)
        self.assertEqual(result["completeClosedBarCounts"]["H4"], 49)

    def test_untrusted_vendor_claims_cannot_enable(self):
        doc = candidate(12000)
        doc.update({"priceBasis": "BID", "licensed": True,
                    "cloudUseApproved": True, "researchEligible": True,
                    "signal": "BUY", "executable": True,
                    "sessionVerified": True, "paperOrdersAllowed": True})
        self.assert_quarantine(audit(doc))

    def test_bad_source_and_payload_are_rejected(self):
        for doc in (None, {}, [], {"provider": "OTHER", "symbol": "XAUUSD.FOREX",
                                   "interval": "1m", "candles": []}):
            self.assert_quarantine(audit(doc))

    def test_reject_unclear_utc_invalid_prices_and_unclosed_minutes(self):
        for mutation, error in (
            (lambda d: d["candles"][0].update(openTime="2026-11-02 00:00:00"),
             "HISTORY_1M_UTC_INVALID"),
            (lambda d: d["candles"][0].update(openTime="2026-11-02T00:00:30Z"),
             "HISTORY_1M_TIME_NOT_MINUTE_ALIGNED"),
            (lambda d: d["candles"][0].update(open=True), "HISTORY_INVALID_OHLC_TYPE"),
            (lambda d: d["candles"][0].update(high=3900), "HISTORY_INVALID_OHLC_RANGE"),
            (lambda d: d["candles"][0].update(close=float("nan")), "HISTORY_INVALID_OHLC_VALUE"),
            (lambda d: d["candles"][0].update(openTime=NOW.isoformat().replace("+00:00", "Z")),
             "HISTORY_UNCLOSED_OR_FUTURE_MINUTE"),
            (lambda d: d["candles"][1].update(openTime=d["candles"][0]["openTime"]),
             "HISTORY_1M_DUPLICATE_OR_NONMONOTONIC"),
        ):
            with self.subTest(error=error):
                doc = candidate(5)
                mutation(doc)
                result = audit(doc)
                self.assert_quarantine(result)
                self.assertEqual(result["blockingReasons"], [error])

    def test_no_provider_calls_and_no_secret_exposure(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = audit(candidate(12000))
        self.assert_quarantine(result)
        self.assertNotIn("Bearer ", repr(result))
        self.assertNotIn("api_token", repr(result))


if __name__ == "__main__":
    unittest.main()
