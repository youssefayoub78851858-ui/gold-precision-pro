"""No-network, no-execution validation for private sampled spread histogram."""
import copy
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch

from biquote_sampled_spread_buckets import audited_sampled_spread_buckets, BINS

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def make_spreads(values):
    rows = []
    for i, width in enumerate(values):
        tick = START + dt.timedelta(minutes=i*2)
        observed = tick + dt.timedelta(seconds=2)
        bid = 4000.0 + i
        ask = bid + width
        rows.append({
            "tickUTC": tick.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "observedUTC": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bid": bid, "ask": ask, "spread": round(ask-bid, 8),
            "privateSecret": "DO_NOT_PRINT_OR_STORE_IN_LOGS"
        })
    return {"schema": 1, "source": "BIQUOTE_UNVERIFIED_UPSTREAM_MT5",
            "quoteObservations": rows, "privatePath": "/var/data/SECRET_BROKER"}


class SampledSpreadTests(unittest.TestCase):
    def assert_safe(self, r):
        self.assertEqual(r["signal"], "WAIT")
        self.assertFalse(r["executable"])
        self.assertFalse(r["paperOrdersAllowed"])
        self.assertFalse(r["liveOrdersAllowed"])
        self.assertFalse(r["sourceRightsVerified"])
        self.assertFalse(r["brokerCommissionSlippageVerified"])
        self.assertFalse(r["historicalBidAskOHLCVerified"])
        self.assertFalse(r["independentNetExpectancyVerified"])
        self.assertEqual(set(r["buckets"]), set(BINS))
        s=json.dumps(r)
        for term in ('"bid"', '"ask"', '"spread"', "4000", "SECRET_BROKER",
                     "DO_NOT_PRINT_OR_STORE", "2026-11-18T08"):
            self.assertNotIn(term, s)

    def test_no_quotes_and_all_spread_ranges(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            empty = audited_sampled_spread_buckets(make_spreads([]))
            self.assert_safe(empty)
            self.assertEqual(empty["status"], "NO_RECORDED_QUOTES")
            self.assertEqual(empty["sourceQuoteSamples"], 0)
            widths = [0.0,0.25,0.26,0.5,0.51,1,1.01,2,2.01,5,5.01]
            record = audited_sampled_spread_buckets(make_spreads(widths))
        self.assert_safe(record)
        self.assertEqual(record["status"], "OBSERVED_SPARSE_QUOTES_ONLY")
        self.assertEqual(record["sourceQuoteSamples"], len(widths))
        self.assertEqual(list(record["buckets"].values()), [2,2,2,2,2,1])
        self.assertEqual(sum(record["buckets"].values()), len(widths))
        self.assertTrue(record["sampleIntervalNotContinuousTickFeed"])

    def test_corrupt_inputs_quarantined_no_partial_or_price_leaks(self):
        base=make_spreads([.25,.4,.8])
        changes=[
            lambda x:x["quoteObservations"][0].update({"spread": 4.0}),
            lambda x:x["quoteObservations"][1].update({"ask": 0}),
            lambda x:x["quoteObservations"][1].update({"ask": 3999.0}),
            lambda x:x["quoteObservations"][1].update({"spread": float("nan")}),
            lambda x:x["quoteObservations"][0].update({"bid": False}),
            lambda x:x["quoteObservations"][2].update({"tickUTC":x["quoteObservations"][1]["tickUTC"]}),
            lambda x:x["quoteObservations"][2].update({"observedUTC":"2026-11-18T08:20:00Z"}),
            lambda x:x.update({"source":"FAKE_LICENSED_BROKER"}),
            lambda x:x.update({"schema":2}),
            lambda x:x.update({"quoteObservations":"NOT_QUOTES"}),
            lambda x:x["quoteObservations"].append({"secret":"ONLY_SECRET"}),
        ]
        for change in changes:
            data=copy.deepcopy(base)
            change(data)
            r=audited_sampled_spread_buckets(data)
            self.assert_safe(r)
            self.assertEqual(r["status"], "INVALID_ARCHIVE_WAIT")
            self.assertEqual(r["sourceQuoteSamples"], 0)
            self.assertEqual(sum(r["buckets"].values()), 0)

    def test_cap_and_no_trading_authority(self):
        record=make_spreads([.4])
        record["quoteObservations"] *= 10001
        self.assertEqual(audited_sampled_spread_buckets(record)["status"],"INVALID_ARCHIVE_WAIT")
        self.assertEqual(audited_sampled_spread_buckets({"quoteObservations":[]})["status"],
                         "INVALID_ARCHIVE_WAIT")


if __name__ == "__main__":
    unittest.main()
