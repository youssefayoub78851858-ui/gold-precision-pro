"""Synthetic fixtures only. Never call BiQuote, no subscription or orders."""
import copy
import datetime as dt
import json
import os
import pathlib
import socket
import stat
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import (
    FILE, START, ingest, inspect_metadata, load_vault
)

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,19,3,5,10,tzinfo=UTC)
def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")
def candle(t,p):
    return {"openTime":iso(t),"open":p,"high":p+0.4,"low":p-0.25,
            "close":p+0.1,"isOpen":False,"volume":0,"tickVolume":4}
def envelope(tf, bars):
    return {"symbol":"XAUUSD","interval":{"M15":"15m","H1":"1h","H4":"4h"}[tf],
            "bars":list(reversed(bars))}
def sample(now=NOW):
    # Constant-width, non-market synthetic time grid; this is ONLY for
    # testing ingestion. Do not infer a real broker session calendar.
    start=dt.datetime(2026,11,16,tzinfo=UTC)
    m15=[]
    t=start
    while t+dt.timedelta(minutes=15)<=now:
        i=len(m15);p=3900+i*0.08
        m15.append(candle(t,p))
        t+=dt.timedelta(minutes=15)
    h1,h4=[],[]
    for factor,dest in [(4,h1),(16,h4)]:
        for i in range(0,len(m15),factor):
            group=m15[i:i+factor]
            if len(group)<factor:break
            dest.append({"openTime":group[0]["openTime"],"open":group[0]["open"],
                "high":max(b["high"] for b in group),
                "low":min(b["low"] for b in group),
                "close":group[-1]["close"],"volume":0,
                "tickVolume":sum(b["tickVolume"] for b in group),
                "isOpen":False})
    return {"source":"BiQuote",
        "quote":{"symbol":"XAUUSD","bid":3901,"ask":3901.3,
            "mid":3901.15,"spread":0.3,"marketState":"open",
            "stale":False,"timestamp":iso(now-dt.timedelta(seconds=3))},
        "frames":{"M15":envelope("M15",m15[-192:]),
                  "H1":envelope("H1",h1[-168:]),
                  "H4":envelope("H4",h4[-180:])}}

class ForwardVault(unittest.TestCase):
    def setUp(self):
        self.base=tempfile.TemporaryDirectory(prefix="gpp-forward-vault-tests-")
        self.root=pathlib.Path(self.base.name)
        self.folder=self.root/"private-candles"
        self.s=sample()
    def tearDown(self):
        self.base.cleanup()
    def safe(self,result):
        self.assertEqual(result["signal"],"WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertFalse(result["researchEligible"])
        self.assertEqual(result["providerRequestsMade"],0)
        self.assertEqual(result["ordersSent"],0)
        self.assertFalse(result["independentBrokerEntitlementVerified"])
        self.assertFalse(result["independentSessionCalendarVerified"])
        self.assertFalse(result["historicalBidAskOhlcAvailable"])

    def test_true_future_boundary_private_hash_no_duplicate_and_restarts(self):
        self.safe(inspect_metadata(self.folder))
        self.assertEqual(inspect_metadata(self.folder)["counts"]["M15"],0)
        with patch.object(socket,"socket",side_effect=AssertionError("NETWORK_NOT_ALLOWED")):
            first=ingest(self.folder,self.s,received_utc=iso(NOW))
        self.safe(first)
        self.assertEqual(first["status"],"PRIVATE_FORWARD_CAPTURE_SAVED")
        self.assertGreater(first["newClosedBars"]["M15"],90)
        self.assertGreater(first["newClosedBars"]["H1"],20)
        self.assertGreater(first["newClosedBars"]["H4"],4)
        self.assertEqual(first["spreadQuoteSamples"],1)
        self.assertTrue(first["sourceMarketDataPersistedToPrivateVault"])
        self.assertFalse(first["independentProfitabilityProven"])
        self.assertFalse(first["rawDataReturnedToCaller"])
        doc=load_vault(self.folder)
        self.assertTrue(all(x["openTime"]>=iso(START) for tf in ("M15","H1","H4")
                            for x in doc["closed"][tf]))
        self.assertEqual(doc["brokerRightsVerified"],False)
        self.assertEqual(doc["sessionVerified"],False)
        self.assertEqual(doc["priceBasis"],"BIQUOTE_MID_POSSIBLE_INITIAL_BID_HISTORY_SEED")
        self.assertEqual(len(doc["quoteObservations"]),1)
        self.assertEqual(os.stat(self.folder).st_mode & 0o077,0)
        self.assertEqual(os.stat(self.folder/FILE).st_mode & 0o077,0)
        self.assertEqual(inspect_metadata(self.folder)["counts"],first["totals"])
        again=ingest(self.folder,self.s,received_utc=iso(NOW))
        self.safe(again)
        self.assertEqual(again["status"],"NO_NEW_BARS")
        self.assertEqual(again["newClosedBars"],{"M15":0,"H1":0,"H4":0})
        self.assertEqual(load_vault(self.folder),doc)

        later=NOW+dt.timedelta(minutes=17)
        extended=sample(later)
        advanced=ingest(self.folder,extended,received_utc=iso(later))
        self.safe(advanced)
        self.assertGreater(advanced["newClosedBars"]["M15"],0)
        self.assertEqual(len(load_vault(self.folder)["quoteObservations"]),2)

    def test_candle_revision_rejected_without_rewriting_archive(self):
        ingest(self.folder,self.s,received_utc=iso(NOW))
        before=(self.folder/FILE).read_bytes()
        altered=copy.deepcopy(self.s)
        # Mutate latest M15 after capture; both OHLC still valid.
        altered["frames"]["M15"]["bars"][0]["high"] += 3
        # Full H1/H4 overlap must not match; failure precedes archive write.
        with self.assertRaisesRegex(ValueError,"MISMATCH|REVISED"):
            ingest(self.folder,altered,received_utc=iso(NOW))
        self.assertEqual((self.folder/FILE).read_bytes(),before)

    def test_interior_gap_does_not_get_filled(self):
        altered=copy.deepcopy(self.s)
        # One M15 member missing, H1/H4 remain source-observed.
        altered["frames"]["M15"]["bars"].pop(8)
        r=ingest(self.folder,altered,received_utc=iso(NOW))
        self.safe(r)
        self.assertGreater(r["crossFrameIncompleteM15"]["H1"],0)
        self.assertGreater(r["crossFrameIncompleteM15"]["H4"],0)
        rows=load_vault(self.folder)["closed"]["M15"]
        self.assertEqual(len(rows),r["totals"]["M15"])
        self.assertEqual(r["status"],"PRIVATE_FORWARD_CAPTURE_SAVED")

    def test_stale_future_open_and_invalid_quote_fail_before_disk(self):
        for modify in (
            lambda s:s["quote"].update({"stale":True}),
            lambda s:s["quote"].update({"ask":3900}),
            lambda s:s["quote"].update({"timestamp":"2026-11-19T03:04:00Z"}),
            lambda s:s["quote"].update({"timestamp":"2026-11-19T03:06:00Z"}),
            lambda s:s["quote"].update({"marketState":"closed"}),
            lambda s:s["frames"]["M15"]["bars"][1].update({"isOpen":True}),
            lambda s:s["frames"]["H1"]["bars"][0].update({"close":10000,"high":10000}),
        ):
            c=copy.deepcopy(self.s)
            modify(c)
            with self.assertRaises(ValueError):
                ingest(self.folder,c,received_utc=iso(NOW))
            self.assertFalse((self.folder/FILE).exists())

    def test_cannot_import_predeclared_past_or_impersonate_claims(self):
        with self.assertRaisesRegex(ValueError,"FORWARD_HOLDOUT_NOT_STARTED"):
            ingest(self.folder,self.s,received_utc="2026-11-17T18:00:00Z")
        c=copy.deepcopy(self.s)
        c["source"]="SIMULATED"
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_SOURCE_ENVELOPE"):
            ingest(self.folder,c,received_utc=iso(NOW))
        c=copy.deepcopy(self.s)
        c["rightsVerified"]=True
        with self.assertRaises(ValueError):
            ingest(self.folder,c,received_utc=iso(NOW))
        self.assertEqual(inspect_metadata(self.folder)["counts"]["M15"],0)

    def test_private_file_integrity_and_symlink_denial(self):
        ingest(self.folder,self.s,received_utc=iso(NOW))
        target=self.folder/FILE
        raw=target.read_text()
        env=json.loads(raw)
        env["payload"]["closed"]["M15"][-1]["close"]+=100
        target.write_text(json.dumps(env))
        with self.assertRaisesRegex(ValueError,"VAULT_TAMPER_OR_HASH_MISMATCH"):
            load_vault(self.folder)
        target.write_text(raw)
        target.chmod(0o644)
        with self.assertRaisesRegex(ValueError,"UNSAFE_PERMISSIONS"):
            load_vault(self.folder)
        target.chmod(0o600)
        target.unlink()
        outside=self.root/"outside.txt"
        outside.write_text(raw)
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,"SYMLINK"):
            load_vault(self.folder)
        target.unlink()
        self.folder.chmod(0o755)
        with self.assertRaisesRegex(ValueError,"VAULT_DIR_NOT_OWNER_ONLY"):
            load_vault(self.folder)
        self.folder.chmod(0o700)

if __name__=="__main__":
    unittest.main()
