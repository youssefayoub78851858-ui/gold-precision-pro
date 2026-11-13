"""Synthetic, no-vendor validation of EODHD REST 1m schema."""
import datetime as dt
import unittest
from unittest.mock import patch
from eodhd_historical_raw_adapter import review_raw_eodhd_intraday_1m

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 2, tzinfo=UTC)
NOW = START + dt.timedelta(days=20)


def rows(count=12000):
    data = []
    for i in range(count):
        instant = START + dt.timedelta(minutes=i)
        data.append({"timestamp": int(instant.timestamp()), "gmtoffset": 0,
                     "datetime": instant.strftime("%Y-%m-%d %H:%M:%S"),
                     "open": 4000.1, "high": 4000.3,
                     "low": 3999.8, "close": 4000.2, "volume": 0})
    return data


def review(data):
    return review_raw_eodhd_intraday_1m(data, as_of=NOW)


class RawEodhdHistoryQuarantine(unittest.TestCase):
    def check_wait(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["readyForPaper"])
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["mayMergeWithLiveBidAsk"])
        self.assertEqual(result["sourceRequestsMade"], 0)
        self.assertEqual(result["payments"], 0)
        self.assertEqual(result["secretReads"], 0)

    def test_utc_rest_schema_is_only_geometric_warmup(self):
        out = review(rows())
        self.check_wait(out)
        self.assertTrue(out["offlineRawPayloadValidated"])
        self.assertEqual(out["completeClosedBarCounts"], {
            "M15": 800, "H1": 200, "H4": 50})
        self.assertFalse(out["historicalConventionVerified"])
        self.assertIn("HISTORICAL_PRICE_BASIS_AND_STREAM_BID_ASK_PARITY_UNVERIFIED",
                      out["blockingReasons"])

    def test_missing_minute_blocks_h4_without_filling(self):
        sample = rows()
        del sample[15]
        result = review(sample)
        self.check_wait(result)
        self.assertEqual(result["completeClosedBarCounts"]["H4"], 49)
        self.assertEqual(result["numberOfUnclassifiedDiscontinuities"], 1)

    def test_conflicting_timestamps_rejected(self):
        for key, value, reason in (
            ("timestamp", 1793577660000, "RAW_HISTORY_TIMESTAMP_DATETIME_CONFLICT"),
            ("gmtoffset", 3600, "RAW_HISTORY_UNVERIFIED_GMT_OFFSET"),
            ("gmtoffset", True, "RAW_HISTORY_UNVERIFIED_GMT_OFFSET"),
            ("datetime", "2026-11-02 00:02:00", "RAW_HISTORY_TIMESTAMP_DATETIME_CONFLICT"),
            ("datetime", "2026-11-02T00:00:00Z", "RAW_HISTORY_DATETIME_INVALID"),
        ):
            with self.subTest(key=key):
                sample = rows(2)
                sample[0][key] = value
                result = review(sample)
                self.check_wait(result)
                self.assertEqual(result["blockingReasons"], [reason])

    def test_bad_prices_rejected_by_central_quality_gate(self):
        for key, value, reason in (
            ("open", -1, "HISTORY_INVALID_OHLC_VALUE"),
            ("high", float("nan"), "HISTORY_INVALID_OHLC_VALUE"),
            ("close", True, "HISTORY_INVALID_OHLC_TYPE"),
        ):
            with self.subTest(key=key):
                sample = rows(3)
                sample[1][key] = value
                result = review(sample)
                self.check_wait(result)
                self.assertEqual(result["blockingReasons"], [reason])

    def test_empty_wrong_shapes_and_duplicates_fail(self):
        for bad in (None, {}, [], [{"timestamp": 1}], "not JSON array"):
            self.check_wait(review(bad))
        sample = rows(3)
        sample[1] = sample[0].copy()
        result = review(sample)
        self.check_wait(result)
        self.assertEqual(result["blockingReasons"],
                         ["HISTORY_1M_DUPLICATE_OR_NONMONOTONIC"])

    def test_untrusted_licensing_claims_cannot_enable(self):
        sample = rows()
        sample[0].update(priceBasis="BID", licensed=True, executable=True)
        self.check_wait(review(sample))

    def test_no_provider_network_or_credentials(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = review(rows(240))
        self.check_wait(result)
        self.assertNotIn("Bearer ", repr(result))
        self.assertNotIn("api_token", repr(result))


if __name__ == "__main__":
    unittest.main()
