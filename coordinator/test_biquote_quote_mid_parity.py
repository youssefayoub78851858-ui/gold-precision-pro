"""Synthetic-only checks for sealed BiQuote tick MID / closed OHLC geometry."""
import copy
import json
import pathlib
import socket
import unittest
from unittest.mock import patch

from biquote_quote_mid_parity import audit_closed_quote_mid_parity


def sample():
    bar={"openTime":"2026-11-18T08:00:00Z",
         "open":4000.0,"high":4000.5,"low":3999.5,"close":4000.2}
    return {
        "schema":1,"source":"BIQUOTE_UNVERIFIED_UPSTREAM_MT5",
        "closed":{"M15":[copy.deepcopy(bar)],
                  "H1":[copy.deepcopy(bar)],"H4":[copy.deepcopy(bar)]},
        "quoteObservations":[
            {"tickUTC":"2026-11-18T08:01:00.500Z",
             "observedUTC":"2026-11-18T08:01:02.000Z",
             "bid":4000.1,"ask":4000.3},
            {"tickUTC":"2026-11-18T08:15:00Z",
             "observedUTC":"2026-11-18T08:15:01Z",
             "bid":4000.1,"ask":4000.3}
        ],
        "secret":"DO_NOT_EXPOSE_PRIVATE"
    }


class QuoteMidParityTests(unittest.TestCase):
    def checked(self, record):
        self.assertEqual(record["signal"],"WAIT")
        self.assertFalse(record["executable"])
        self.assertFalse(record["paperOrdersAllowed"])
        self.assertFalse(record["liveOrdersAllowed"])
        self.assertFalse(record["brokerRightsVerified"])
        self.assertFalse(record["independentBrokerPriceParityVerified"])
        for word in ('"bid"','"ask"','"open"','"high"','"low"','"close"',
                     'DO_NOT_EXPOSE_PRIVATE','4000.1','4000.2','3999.5',
                     '2026-11-18T08'):
            self.assertNotIn(word,json.dumps(record))
        return record

    def test_coordinator_docker_must_package_private_mid_parity_checker(self):
        docker=(pathlib.Path(__file__).resolve().parent/"Dockerfile").read_text()
        self.assertIn("biquote_quote_mid_parity.py",docker)
        self.assertIn("biquote_private_forward_vault.py",docker)
        vault=(pathlib.Path(__file__).resolve().parent/
               "biquote_private_forward_vault.py").read_text()
        self.assertIn("audit_closed_quote_mid_parity(v)",vault)

    def test_quote_mid_in_closed_candle_bounds_counts_only(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            r=self.checked(audit_closed_quote_mid_parity(sample()))
        self.assertEqual(r["status"],"CONSISTENT_OBSERVED_SAMPLES_ONLY")
        self.assertEqual(r["sourceQuoteSamples"],2)
        m=r["frames"]["M15"]
        self.assertEqual(m["comparableQuoteSamples"],1)
        self.assertEqual(m["withinClosedOHLC"],1)
        self.assertEqual(m["outsideClosedOHLC"],0)
        self.assertEqual(m["distinctComparableClosedBars"],1)
        self.assertEqual(m["notInArchivedClosedBars"],1)
        self.assertEqual(r["frames"]["H1"]["comparableQuoteSamples"],2)
        self.assertEqual(r["frames"]["H4"]["comparableQuoteSamples"],2)

    def test_contradictory_tick_cannot_be_called_clean(self):
        data=sample()
        data["quoteObservations"][0]["bid"]=4008.0
        data["quoteObservations"][0]["ask"]=4008.5
        out=self.checked(audit_closed_quote_mid_parity(data))
        self.assertEqual(out["status"],"OBSERVED_MID_OUTSIDE_CLOSED_OHLC")
        for tf in ("M15","H1","H4"):
            self.assertEqual(out["frames"][tf]["outsideClosedOHLC"],1)
            self.assertEqual(out["frames"][tf]["withinClosedOHLC"],int(tf!="M15"))

    def test_no_closed_candle_is_not_assumed_to_match(self):
        data=sample()
        data["closed"]={tf:[] for tf in ("M15","H1","H4")}
        out=self.checked(audit_closed_quote_mid_parity(data))
        self.assertEqual(out["status"],"NO_COMPARABLE_CLOSED_SAMPLES")
        for x in out["frames"].values():
            self.assertEqual(x["comparableQuoteSamples"],0)
            self.assertEqual(x["notInArchivedClosedBars"],2)

    def test_bad_receipt_price_grid_duplicate_and_tampering_fail_closed(self):
        for mutation in (
            lambda x:x["quoteObservations"][0].update(
                {"observedUTC":"2026-11-18T08:00:00Z"}),
            lambda x:x["quoteObservations"][0].update({"ask":0}),
            lambda x:x["quoteObservations"][0].update({"bid":4005}),
            lambda x:x["closed"]["H4"][0].update({"high":0}),
            lambda x:x["closed"]["M15"].append(copy.deepcopy(x["closed"]["M15"][0])),
            lambda x:x["closed"]["H1"][0].update({"openTime":"2026-11-18T08:11:00Z"}),
            lambda x:x.update({"source":"FAKE"}),
            lambda x:x.update({"quoteObservations":"SECRET_NOT_A_LIST"}),
        ):
            data=sample()
            mutation(data)
            result=self.checked(audit_closed_quote_mid_parity(data))
            self.assertEqual(result["status"],"INVALID_ARCHIVE_WAIT")
            self.assertEqual(result["sourceQuoteSamples"],0)
            self.assertEqual(result["frames"],{})

    def test_quoted_values_never_pass_through_report(self):
        data=sample()
        data["quoteObservations"][0]["secret"]="HIDDEN_BROKER_CARD"
        text=json.dumps(self.checked(audit_closed_quote_mid_parity(data)))
        self.assertNotIn("HIDDEN_BROKER_CARD",text)
        self.assertNotIn("4008",text)


if __name__=="__main__":
    unittest.main()
