"""Massive adapter tests consume fixtures only and never use a provider client."""
import datetime as dt
import unittest

from massive_xauusd_fixture_adapter import (
    INTERVALS, aggregate_spec, build_synthetic_gate_payload,
    normalize_fixture_response,
)
from xauusd_feed_gate import SourcePolicy, intake_payload


class MassiveXauUsdOfflineAdapterTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 11, 12, 15, tzinfo=dt.timezone.utc)
        self.opens = {"15min": "2026-11-11T12:00:00Z",
                      "1h": "2026-11-11T11:00:00Z",
                      "4h": "2026-11-11T08:00:00Z"}
        self.responses = {
            interval: {"status": "OK", "ticker": "C:XAUUSD", "results": [{
                "t": int(dt.datetime.fromisoformat(opened.replace("Z", "+00:00")).timestamp() * 1000),
                "o": 2000, "h": 2002, "l": 1999, "c": 2001, "v": 500, "n": 8,
            }]} for interval, opened in self.opens.items()
        }

    def test_supported_intervals_map_to_documented_minute_and_hour_bars(self):
        self.assertEqual(aggregate_spec("15min"),
                         {"symbol": "C:XAUUSD", "multiplier": 15, "timespan": "minute"})
        self.assertEqual(aggregate_spec("1h")["multiplier"], 1)
        self.assertEqual(aggregate_spec("4h")["multiplier"], 4)
        self.assertEqual(aggregate_spec("4h")["timespan"], "hour")
        with self.assertRaises(ValueError):
            aggregate_spec("1min")

    def test_payload_stays_synthetic_and_gate_never_promotes_it(self):
        expected = {interval: [opened] for interval, opened in self.opens.items()}
        payload = build_synthetic_gate_payload(self.responses,
                                                "2026-11-11T12:15:00Z", expected)
        result = intake_payload(payload, self.now, SourcePolicy())
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(result["researchEligible"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["sourceRequestsMade"], 0)

    def test_quote_count_is_not_mislabeled_as_trade_volume(self):
        bar = normalize_fixture_response("15min", self.responses["15min"])["candles"][0]
        self.assertNotIn("volume", bar)
        self.assertEqual(bar["close"], 2001.0)

    def test_unavailable_wrong_ticker_bad_ohlc_and_misaligned_timestamp_rejected(self):
        for response in ({"status": "NOT_AUTHORIZED", "ticker": "C:XAUUSD", "results": []},
                         {"status": "OK", "ticker": "C:EURUSD", "results": [{"t": 0, "o": 1, "h": 1, "l": 1, "c": 1}]}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                normalize_fixture_response("15min", response)
        bad = {**self.responses["15min"], "results": [{**self.responses["15min"]["results"][0], "h": 1998}]}
        with self.assertRaises(ValueError):
            normalize_fixture_response("15min", bad)
        misaligned = {**self.responses["15min"], "results": [{**self.responses["15min"]["results"][0], "t": self.responses["15min"]["results"][0]["t"] + 1000}]}
        with self.assertRaises(ValueError):
            normalize_fixture_response("15min", misaligned)

    def test_missing_interval_or_missing_expected_schedule_is_not_filled(self):
        expected = {interval: [opened] for interval, opened in self.opens.items()}
        incomplete = dict(self.responses)
        del incomplete["4h"]
        with self.assertRaises(ValueError):
            build_synthetic_gate_payload(incomplete, "2026-11-11T12:15:00Z", expected)
        expected["1h"] = []
        payload = build_synthetic_gate_payload(self.responses, "2026-11-11T12:15:00Z", expected)
        result = intake_payload(payload, self.now, SourcePolicy())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["researchEligible"])
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])


if __name__ == "__main__":
    unittest.main()
