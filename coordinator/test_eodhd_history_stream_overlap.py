"""No-network, synthetic checks for delayed REST / live Bid-Ask overlap."""
from __future__ import annotations
import copy
import datetime as dt
import unittest
from unittest.mock import patch

from eodhd_history_stream_overlap import compare_eodhd_rest_to_stream

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 2, tzinfo=UTC)
NOW = START + dt.timedelta(days=20)


def sample(minutes=240):
    raw = []
    for i in range(minutes):
        t = START + dt.timedelta(minutes=i)
        # Nonconstant prices check 15-minute OHLC (not just close).
        p = 4000 + (i % 29) / 10
        raw.append({
            "timestamp": int(t.timestamp()),
            "datetime": t.strftime("%Y-%m-%d %H:%M:%S"),
            "gmtoffset": 0,
            "open": p, "high": p + 0.1, "low": p - 0.1, "close": p + 0.02,
        })

    def bars(offset):
        out = []
        for start in range(0, minutes, 15):
            if start + 15 > minutes:
                continue
            rows = raw[start:start+15]
            t = START + dt.timedelta(minutes=start)
            out.append({
                "openTime": t.isoformat().replace("+00:00", "Z"),
                "open": rows[0]["open"] + offset,
                "high": max(r["high"] for r in rows) + offset,
                "low": min(r["low"] for r in rows) + offset,
                "close": rows[-1]["close"] + offset,
            })
        return out

    def aggregate(source, factor):
        out = []
        for i in range(0, len(source), factor):
            group = source[i:i+factor]
            if len(group) != factor:
                continue
            out.append({
                "openTime": group[0]["openTime"],
                "open": group[0]["open"],
                "high": max(x["high"] for x in group),
                "low": min(x["low"] for x in group),
                "close": group[-1]["close"],
            })
        return {"M15": source, "H1": out if factor == 4 else [],
                "H4": out if factor == 16 else []}

    frames = {}
    for name, offset in (("bidFrames", 0), ("frames", 0.2), ("askFrames", 0.4)):
        one = bars(offset)
        frames[name] = {
            "M15": one,
            "H1": aggregate(one, 4)["H1"],
            "H4": aggregate(one, 16)["H4"],
        }
    snapshot = {
        "provider": "EODHD", "instrument": "XAU/USD",
        "quoteType": "INDICATIVE_MIDQUOTE_OHLC",
        "mode": "REVIEW_ONLY", "signal": "WAIT",
        "executable": False, "researchEligible": False,
        "readyForTrading": False, **frames,
    }
    return raw, snapshot


def review(history, stream):
    return compare_eodhd_rest_to_stream(history, stream, as_of=NOW)


class HistoryStreamOverlap(unittest.TestCase):
    def assert_safe(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["researchEligible"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertFalse(result["mayMergeHistoricalAndStreamBars"])
        self.assertFalse(result["historicalPriceBasisVerified"])
        self.assertEqual(result["sourceRequestsMade"], 0)
        self.assertEqual(result["payments"], 0)
        self.assertEqual(result["secretReads"], 0)

    def test_perfect_bid_match_is_not_licence_or_research_authorization(self):
        raw, stream = sample()
        report = review(raw, stream)
        self.assert_safe(report)
        self.assertEqual(report["matchedCompleteM15"], 16)
        self.assertEqual(report["closestObservedSeriesOnlyNotVerifiedBasis"], "BID")
        self.assertEqual(report["differencesUSDPerOunce"]["BID"]["maximumAbsoluteOhlcDifference"], 0)
        self.assertEqual(report["differencesUSDPerOunce"]["ASK"]["medianAbsoluteOhlcDifference"], 0.4)
        self.assertTrue(report["informationalComparisonOnly"])

    def test_mid_match_merely_reports_closest_series(self):
        raw, stream = sample()
        for row in raw:
            for field in ("open", "high", "low", "close"):
                row[field] += 0.2
        r = review(raw, stream)
        self.assert_safe(r)
        self.assertEqual(r["closestObservedSeriesOnlyNotVerifiedBasis"], "MID")
        self.assertEqual(r["differencesUSDPerOunce"]["MID"]["medianAbsoluteOhlcDifference"], 0)

    def test_sparse_complete_utc_overlap_still_waits(self):
        raw, stream = sample()
        stream["bidFrames"]["M15"] = stream["bidFrames"]["M15"][:3]
        stream["frames"]["M15"] = stream["frames"]["M15"][:3]
        stream["askFrames"]["M15"] = stream["askFrames"]["M15"][:3]
        for name in ("bidFrames", "frames", "askFrames"):
            stream[name]["H1"] = []
            stream[name]["H4"] = []
        out = review(raw, stream)
        self.assert_safe(out)
        self.assertEqual(out["matchedCompleteM15"], 3)
        self.assertIn("INSUFFICIENT_SAME_UTC_M15_OVERLAP", out["blockingReasons"])
        self.assertNotIn("differencesUSDPerOunce", out)

    def test_no_overlap_never_invents_comparison(self):
        raw, stream = sample()
        for name in ("bidFrames", "frames", "askFrames"):
            for tf in ("M15", "H1", "H4"):
                for row in stream[name][tf]:
                    old = dt.datetime.fromisoformat(row["openTime"].replace("Z", "+00:00"))
                    row["openTime"] = (old + dt.timedelta(days=4)).isoformat().replace("+00:00", "Z")
        out = review(raw, stream)
        self.assert_safe(out)
        self.assertEqual(out["matchedCompleteM15"], 0)

    def test_incomplete_minute_group_excluded_not_backfilled(self):
        raw, stream = sample()
        del raw[2]  # one minute removed from an M15 / H1 / H4 group
        out = review(raw, stream)
        self.assert_safe(out)
        self.assertEqual(out["matchedCompleteM15"], 15)
        self.assertEqual(out["historicalCompleteM15"], 15)
        self.assertIn("NUMERICAL_OVERLAP_OBSERVED_BUT_BASIS_NOT_AUTHORIZED", out["blockingReasons"])

    def test_reject_fake_grants_or_bad_stream_geometry(self):
        raw, stream = sample()
        forged = copy.deepcopy(stream)
        forged["researchEligible"] = True
        self.assert_safe(review(raw, forged))
        self.assertEqual(review(raw, forged)["blockingReasons"][0],
                         "STREAM_SNAPSHOT_IDENTITY_OR_SAFETY_INVALID")
        forged = copy.deepcopy(stream)
        forged["bidFrames"]["H4"][0]["high"] += 1
        self.assertEqual(review(raw, forged)["blockingReasons"][0],
                         "STREAM_BID_ASK_GEOMETRY_REJECTED")

    def test_bad_rest_timestamp_cannot_pass(self):
        raw, stream = sample()
        raw[4]["timestamp"] += 60
        result = review(raw, stream)
        self.assert_safe(result)
        self.assertEqual(result["blockingReasons"][0], "HISTORICAL_REST_INPUT_REJECTED")
        self.assertEqual(result["matchedCompleteM15"], 0)

    def test_future_unclosed_rejected(self):
        raw, stream = sample()
        raw[-1]["timestamp"] = int(NOW.timestamp())
        raw[-1]["datetime"] = NOW.strftime("%Y-%m-%d %H:%M:%S")
        self.assert_safe(review(raw, stream))
        self.assertEqual(review(raw, stream)["blockingReasons"][0],
                         "HISTORICAL_REST_INPUT_REJECTED")

    def test_network_never_required(self):
        raw, stream = sample()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = review(raw, stream)
        self.assert_safe(result)
        self.assertNotIn("api_token", repr(result))


if __name__ == "__main__":
    unittest.main()
