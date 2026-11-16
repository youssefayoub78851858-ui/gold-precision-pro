"""Synthetic /v3/quotes historical BBO acceptance: no provider, no secrets."""
import datetime as dt
import unittest

from massive_bbo_history_adapter import review_synthetic_massive_bbo as inspect

UTC = dt.timezone.utc
M15 = 900
BASE = int(dt.datetime(2026, 11, 2, tzinfo=UTC).timestamp())


def payload(*, bars=800):
    rows = []
    # First 480 complete M15 are followed by an assumed 48-hour closure,
    # then 320 complete M15. This is synthetic, NOT a verified session calendar.
    for i in range(bars):
        start = BASE + i * M15 if i < 480 else BASE + 7 * 86400 + (i - 480) * M15
        for minute in range(15):
            second = start + minute * 60 + 30
            bid = 3900.0 + i * 0.001 + minute * 0.02
            rows.append({"participant_timestamp": str(second * 1000000000),
                         "bid_price": bid, "ask_price": bid + 0.4,
                         "bid_exchange": 1, "ask_exchange": 1})
    return {"ticker": "C:XAUUSD", "sourceDataMode": "SYNTHETIC_TEST_ONLY",
            "results": rows}


class MassiveSyntheticHistoricalBBOTests(unittest.TestCase):
    as_of = "2026-11-13T00:00:00Z"

    def test_800_m15_bid_ask_can_build_50_h4_without_faking_weekend(self):
        v = inspect(payload(), as_of_utc=self.as_of)
        self.assertEqual(v["completeClosedBarCounts"], {"M15": 800, "H1": 200, "H4": 50})
        self.assertTrue(v["minimumClosed50H4MetBySyntheticGeometry"])
        self.assertEqual(v["unverifiedM15Discontinuities"], 1)
        self.assertEqual(v["incompleteM15Discarded"], 0)
        for family in ("bidFrames", "askFrames", "midFrames"):
            self.assertEqual(len(v[family]["H4"]), 50)
        for bid, ask, mid in zip(v["bidFrames"]["M15"], v["askFrames"]["M15"], v["midFrames"]["M15"]):
            self.assertLessEqual(bid["high"], ask["high"])
            self.assertEqual(mid["open"], (bid["open"] + ask["open"]) / 2)
        self.assertEqual(v["signal"], "WAIT")
        for key in ("executable", "researchEligible", "licenseVerified",
                    "sameFeedRealtimeParityVerified", "marketHistoryVerified",
                    "paperOrdersAllowed", "quoteActivityIsExecutedVolume",
                    "gcOrderFlowAvailable"):
            self.assertFalse(v[key], key)
        self.assertEqual(v["sourceRequestsMade"], 0)
        self.assertEqual(v["payments"], 0)

    def test_missing_middle_quote_invalidates_m15_and_its_h1_h4(self):
        sample = payload()
        # Two consecutive 60-second steps become 120 seconds: no interpolation.
        del sample["results"][600 * 15 + 7]
        v = inspect(sample, as_of_utc=self.as_of)
        self.assertEqual(v["incompleteM15Discarded"], 1)
        self.assertEqual(v["completeClosedBarCounts"], {"M15": 799, "H1": 199, "H4": 49})
        self.assertFalse(v["minimumClosed50H4MetBySyntheticGeometry"])
        self.assertEqual(v["signal"], "WAIT")

    def test_unsafe_price_timestamp_identity_or_forged_rights_rejected(self):
        for mutate in (
            lambda s: s.update(sourceDataMode="live"),
            lambda s: s.update(ticker="C:EURUSD"),
            lambda s: s.update(researchEligible=True),
            lambda s: s["results"][0].update(ask_price=3890),
            lambda s: s["results"][0].update(participant_timestamp=1.2),
            lambda s: s["results"][0].update(participant_timestamp="123456"),
            lambda s: s["results"][0].update(bid_price=True),
            lambda s: s["results"].reverse(),
        ):
            with self.subTest(mutate=mutate):
                sample = payload(bars=1)
                mutate(sample)
                with self.assertRaises(ValueError):
                    inspect(sample, as_of_utc=self.as_of)

    def test_same_second_bbo_events_preserve_rest_response_order(self):
        sample = payload(bars=1)
        tied = dict(sample["results"][5])
        tied["bid_price"] = 4002.0
        tied["ask_price"] = 4002.4
        sample["results"].insert(6, tied)
        v = inspect(sample, as_of_utc=self.as_of)
        self.assertEqual(v["quotesValidated"], 16)
        self.assertEqual(v["incompleteM15Discarded"], 0)
        self.assertEqual(v["completeClosedBarCounts"]["M15"], 1)
        self.assertEqual(v["bidFrames"]["M15"][0]["high"], 4002.0)
        self.assertEqual(v["askFrames"]["M15"][0]["high"], 4002.4)
        self.assertEqual(v["signal"], "WAIT")
        self.assertFalse(v["executable"])
        # Reversed timestamps, not equal timestamps, must be rejected.
        disordered = payload(bars=1)
        disordered["results"][6], disordered["results"][5] = (
            disordered["results"][5], disordered["results"][6])
        with self.assertRaisesRegex(ValueError, "REVERSED"):
            inspect(disordered, as_of_utc=self.as_of)

    def test_subsecond_asof_accepts_only_observed_quotes_before_exact_boundary(self):
        sample = payload(bars=1)
        transition_ns = (BASE + M15 + 30) * 1_000_000_000 + 400_000_000
        sample["results"].append({
            "participant_timestamp": str(transition_ns),
            "bid_price": 3901.0, "ask_price": 3901.4,
        })
        result = inspect(sample, as_of_utc="2026-11-02T00:15:30.500Z")
        self.assertEqual(result["quotesValidated"], 16)
        self.assertEqual(result["completeClosedBarCounts"]["M15"], 1)
        self.assertEqual(result["incompleteM15Discarded"], 1)
        self.assertFalse(result["researchEligible"])
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_UNCLOSED"):
            inspect(sample, as_of_utc="2026-11-02T00:15:30.400Z")
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_UNCLOSED"):
            inspect(sample, as_of_utc="2026-11-02T00:15:30.399Z")

    def test_sparse_quotes_and_unclosed_candle_are_not_promoted(self):
        sample = payload(bars=1)
        sample["results"] = sample["results"][:3]  # no last-minute quote
        v = inspect(sample, as_of_utc=self.as_of)
        self.assertEqual(v["completeClosedBarCounts"]["M15"], 0)
        self.assertEqual(v["incompleteM15Discarded"], 1)
        self.assertFalse(v["researchEligible"])
        with self.assertRaises(ValueError):
            inspect(payload(bars=1), as_of_utc="2026-11-02T00:14:00Z")


if __name__ == "__main__":
    unittest.main()
