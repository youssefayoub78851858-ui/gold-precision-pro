"""No-network tests for sampled BID/ASK receipt cadence evidence."""
import copy
import datetime as dt
import json
import socket
import unittest
from unittest.mock import patch
from biquote_quote_cadence import audit_quote_cadence, INTERVAL_BINS, LAG_BINS

UTC=dt.timezone.utc
BASE_TIME=dt.datetime(2026,11,18,8,tzinfo=UTC)


def vault(offsets, lags=None):
    if lags is None:
        lags=[1 for _ in offsets]
    quotes=[]
    for i, (minute, lag) in enumerate(zip(offsets,lags)):
        tick=BASE_TIME+dt.timedelta(minutes=minute)
        received=tick+dt.timedelta(seconds=lag)
        bid=3900+i
        ask=bid+.2
        quotes.append({
            "tickUTC":tick.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "observedUTC":received.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bid":bid,"ask":ask,"spread":round(ask-bid,8),
            "apiKey":"PRIVATE_NEVER_OUTPUT"})
    return {"schema":1,"source":"BIQUOTE_UNVERIFIED_UPSTREAM_MT5",
            "quoteObservations":quotes,"private":"SECRET_OWNER_ONLY"}


class QuoteCadenceTests(unittest.TestCase):
    def safety(self, result):
        self.assertEqual(result["signal"],"WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertFalse(result["liveOrdersAllowed"])
        self.assertFalse(result["continuousMarketDataVerified"])
        self.assertFalse(result["missingSamplesAreMarketOutageProof"])
        self.assertFalse(result["longGapsAreBrokerClosures"])
        self.assertFalse(result["brokerRightsVerified"])
        self.assertEqual(set(result["intervalBins"]),set(INTERVAL_BINS))
        self.assertEqual(set(result["quoteReceiptLagBins"]),set(LAG_BINS))
        output=json.dumps(result)
        for secret in ("PRIVATE_NEVER_OUTPUT","SECRET_OWNER_ONLY",
                       '"bid"','"ask"','"spread"','3900',
                       "2026-11-18T08", "apiKey"):
            self.assertNotIn(secret,output)

    def test_empty_single_and_multi_gap_classification(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            zero=audit_quote_cadence(vault([]))
            one=audit_quote_cadence(vault([0]))
            many=audit_quote_cadence(vault([0,2,6,14,34,110],
                                          [1,10,26,1,10,26]))
        self.safety(zero)
        self.assertEqual(zero["status"],"NO_RECORDED_QUOTES")
        self.assertEqual(zero["observedIntervals"],0)
        self.safety(one)
        self.assertEqual(one["sourceQuoteSamples"],1)
        self.assertEqual(one["observedIntervals"],0)
        self.safety(many)
        self.assertEqual(many["status"],"SPARSE_RECEIPT_CADENCE_OBSERVED_ONLY")
        self.assertEqual(many["sourceQuoteSamples"],6)
        self.assertEqual(many["observedIntervals"],5)
        self.assertEqual(list(many["intervalBins"].values()),[1,1,1,1,1])
        self.assertEqual(list(many["quoteReceiptLagBins"].values()),[2,2,2])
        self.assertEqual(sum(many["intervalBins"].values()),5)
        self.assertEqual(sum(many["quoteReceiptLagBins"].values()),6)

    def test_invalid_source_clock_or_quote_quarantines_all_counts(self):
        original=vault([0,2,4])
        modifications=[
            lambda x:x.update({"schema":99}),
            lambda x:x.update({"source":"VERIFIED_BY_TEST"}),
            lambda x:x.update({"quoteObservations":"WRONG"}),
            lambda x:x["quoteObservations"][0].update({"bid":0}),
            lambda x:x["quoteObservations"][0].update({"ask":False}),
            lambda x:x["quoteObservations"][0].update({"spread":3.0}),
            lambda x:x["quoteObservations"][0].update({"observedUTC":"2026-11-18T08:00:40Z"}),
            lambda x:x["quoteObservations"][1].update({"tickUTC":"2026-11-18T08:00:00Z"}),
            lambda x:x["quoteObservations"][1].update({"observedUTC":"2026-11-18T07:59:00Z"}),
            lambda x:x["quoteObservations"][1].update({"observedUTC":"2026-11-18T08:02:99Z"}),
            lambda x:x["quoteObservations"].append({"apiKey":"NO"}),
        ]
        for change in modifications:
            item=copy.deepcopy(original)
            change(item)
            invalid=self.safety(audit_quote_cadence(item))
            self.assertIsNone(invalid)
            r=audit_quote_cadence(item)
            self.assertEqual(r["status"],"INVALID_ARCHIVE_WAIT")
            self.assertEqual(r["sourceQuoteSamples"],0)
            self.assertEqual(sum(r["intervalBins"].values()),0)
            self.assertEqual(sum(r["quoteReceiptLagBins"].values()),0)

    def test_cap_enforced_and_does_not_extrapolate_missing_market_ticks(self):
        sample=vault([0])
        sample["quoteObservations"] *= 10001
        self.safety(audit_quote_cadence(sample))
        self.assertEqual(audit_quote_cadence(sample)["status"],"INVALID_ARCHIVE_WAIT")


if __name__=="__main__":
    unittest.main()
