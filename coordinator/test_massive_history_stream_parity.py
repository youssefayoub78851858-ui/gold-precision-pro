"""Cross-language, zero-network regression for 16 aligned M15 BID/ASK candles."""
from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import subprocess
import unittest
from unittest.mock import patch

from massive_bbo_history_adapter import review_synthetic_massive_bbo
from massive_history_stream_parity import compare_synthetic_history_and_stream

UTC = dt.timezone.utc
BASE = int(dt.datetime(2026, 11, 10, 8, 0, tzinfo=UTC).timestamp())
AS_OF = "2026-11-10T12:01:00Z"
ROOT = pathlib.Path(__file__).resolve().parent
RUNNER = ROOT / "massive_parity_fixture_runner.js"


def create_quotes():
    rows = []
    for i in range(16):
        for minute in range(15):
            ms = (BASE + i * 900 + minute * 60 + 30) * 1000
            bid = 3900.0 + i * .05 + minute * .002
            rows.append({"participant_timestamp": str(ms * 1000000),
                         "bid_price": bid, "ask_price": bid + .4})
    # Closing 16th M15 requires the next M15's first synthetic quote.
    # REST correctly discards the forming 17th bar.
    rows.append({"participant_timestamp": str((BASE + 16 * 900 + 30) * 10**9),
                 "bid_price": 3901.2, "ask_price": 3901.6})
    return rows


def paired(quotes):
    rest = review_synthetic_massive_bbo(
        {"ticker": "C:XAUUSD", "sourceDataMode": "SYNTHETIC_TEST_ONLY", "results": quotes},
        as_of_utc=AS_OF)
    payload = {"ticker": "C:XAUUSD", "sourceDataMode": "SYNTHETIC_TEST_ONLY",
               "asOfUTC": AS_OF, "quotes": quotes}
    result = subprocess.run(["node", str(RUNNER)], input=json.dumps(payload),
                            text=True, capture_output=True, check=True)
    return rest, json.loads(result.stdout)


class MassiveHistoricalStreamingParity(unittest.TestCase):
    def test_16_closed_utc_bid_ask_mid_m15_h1_h4_match_geometry(self):
        rest, stream = paired(create_quotes())
        self.assertEqual(rest["completeClosedBarCounts"], {"M15": 16, "H1": 4, "H4": 1})
        self.assertEqual(rest["incompleteM15Discarded"], 1)
        self.assertEqual([len(stream["frames"][k]) for k in ("M15", "H1", "H4")], [16, 4, 1])
        result = compare_synthetic_history_and_stream(rest, stream)
        self.assertEqual(result["status"], "OFFLINE_NUMERICAL_PARITY_ONLY")
        self.assertEqual(result["mismatchCodes"], [])
        self.assertEqual(result["syntheticBidBarsCompared"], {"M15": 16, "H1": 4, "H4": 1})
        self.assertIs(result["sameFeedProven"], False)
        self.assertIs(result["historyMayMergeWithStream"], False)
        self.assertIs(result["paperOrdersAllowed"], False)
        self.assertEqual(result["signal"], "WAIT")
        self.assertIs(result["executable"], False)
        self.assertEqual(result["providerRequestsMade"], 0)

    def test_tied_timestamp_keeps_distinct_quote_and_does_not_invent_volume(self):
        qs = create_quotes()
        tied = dict(qs[2])
        tied["bid_price"] += .2
        tied["ask_price"] += .2
        qs.insert(3, tied)
        rest, stream = paired(qs)
        result = compare_synthetic_history_and_stream(rest, stream)
        self.assertEqual(result["status"], "OFFLINE_NUMERICAL_PARITY_ONLY")
        self.assertEqual(rest["quotesValidated"], 242)
        self.assertIs(stream["quoteActivityIsTradeVolume"], False)

    def test_modified_ask_and_missing_bar_fail_closed(self):
        rest, stream = paired(create_quotes())
        stream = copy.deepcopy(stream)
        stream["askFrames"]["M15"][4]["close"] += 1
        output = compare_synthetic_history_and_stream(rest, stream)
        self.assertEqual(output["status"], "BLOCKED_SYNTHETIC_PARITY")
        self.assertIn("ASK_M15_OHLC_MISMATCH", output["mismatchCodes"])
        self.assertIs(output["researchEligible"], False)
        stream = paired(create_quotes())[1]
        stream["frames"]["M15"].pop()
        result = compare_synthetic_history_and_stream(rest, stream)
        self.assertIn("MID_M15_COUNT_MISMATCH", result["mismatchCodes"])
        self.assertEqual(result["signal"], "WAIT")

    def test_empty_and_cross_basis_misalignment_never_report_numerical_parity(self):
        rest, stream = paired(create_quotes())
        empty_rest, empty_stream = copy.deepcopy(rest), copy.deepcopy(stream)
        for result, family_names in (
            (empty_rest, ("bidFrames", "askFrames", "midFrames")),
            (empty_stream, ("bidFrames", "askFrames", "frames")),
        ):
            for family in family_names:
                for timeframe in ("M15", "H1", "H4"):
                    result[family][timeframe] = []
        zero = compare_synthetic_history_and_stream(empty_rest, empty_stream)
        self.assertEqual(zero["status"], "BLOCKED_SYNTHETIC_PARITY")
        self.assertIn("REST_NO_CLOSED_BID_ASK_MID_M15", zero["mismatchCodes"])
        self.assertIn("STREAM_NO_CLOSED_BID_ASK_MID_M15", zero["mismatchCodes"])

        # Both historical and live ASK can agree with each other but still
        # disagree with BID/MID about the same M15 boundary.
        bad_rest, bad_stream = copy.deepcopy(rest), copy.deepcopy(stream)
        moved_time = "2026-11-10T08:00:01.000Z"
        bad_rest["askFrames"]["M15"][0]["openTime"] = moved_time
        bad_stream["askFrames"]["M15"][0]["openTime"] = moved_time
        skew = compare_synthetic_history_and_stream(bad_rest, bad_stream)
        self.assertEqual(skew["status"], "BLOCKED_SYNTHETIC_PARITY")
        self.assertIn("REST_M15_FAMILY_TIMESTAMP_SKEW", skew["mismatchCodes"])
        self.assertIn("STREAM_M15_FAMILY_TIMESTAMP_SKEW", skew["mismatchCodes"])
        self.assertFalse(skew["historyMayMergeWithStream"])

        # An empty ASK family cannot pass even though its two copies agree.
        no_ask_rest, no_ask_stream = copy.deepcopy(rest), copy.deepcopy(stream)
        no_ask_rest["askFrames"]["M15"] = []
        no_ask_stream["askFrames"]["M15"] = []
        missing = compare_synthetic_history_and_stream(no_ask_rest, no_ask_stream)
        self.assertEqual(missing["status"], "BLOCKED_SYNTHETIC_PARITY")
        self.assertIn("REST_M15_FAMILY_COUNT_SKEW", missing["mismatchCodes"])

    def test_admission_flags_and_bad_fixture_are_rejected(self):
        rest, stream = paired(create_quotes())
        for key, value in (("mode", "REAL_MARKET_LIVE"),
                           ("executable", True), ("sourceDataMode", "recorded")):
            tampered = copy.deepcopy(stream)
            tampered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare_synthetic_history_and_stream(rest, tampered)
        tampered = copy.deepcopy(rest)
        tampered["sameFeedRealtimeParityVerified"] = True
        with self.assertRaises(ValueError):
            compare_synthetic_history_and_stream(tampered, stream)
        forged = {"ticker": "C:XAUUSD", "sourceDataMode": "live",
                  "asOfUTC": AS_OF, "quotes": create_quotes()}
        proc = subprocess.run(["node", str(RUNNER)], input=json.dumps(forged),
                              text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("3900", proc.stdout + proc.stderr)

    def test_no_network_side_effects_in_pure_comparison(self):
        rest, stream = paired(create_quotes())
        with patch("socket.socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            result = compare_synthetic_history_and_stream(rest, stream)
        self.assertEqual(result["providerRequestsMade"], 0)


if __name__ == "__main__":
    unittest.main()
