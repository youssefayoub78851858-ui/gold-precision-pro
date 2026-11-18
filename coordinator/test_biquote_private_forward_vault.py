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
    FILE, START, ingest, inspect_metadata, load_vault, capture_freshness
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
        empty=inspect_metadata(self.folder)
        self.assertEqual(empty["counts"]["M15"],0)
        self.assertEqual(empty["forwardCoverage"]["M15"]["latestContiguousBars"],0)
        self.assertIsNone(empty["forwardCoverage"]["H4"]["lastClosedUTC"])
        self.assertFalse(empty["tradeSignalReady"])
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
        summary=inspect_metadata(self.folder)
        self.assertEqual(summary["counts"],first["totals"])
        self.assertEqual(summary["forwardCoverage"]["M15"]["closedBars"],
                         first["totals"]["M15"])
        self.assertEqual(summary["forwardCoverage"]["M15"]["unclassifiedGapPairs"],0)
        self.assertEqual(summary["forwardCoverage"]["M15"]["latestContiguousBars"],
                         first["totals"]["M15"])
        self.assertEqual(summary["forwardCoverage"]["M15"]["lastClosedUTC"],
                         "2026-11-19T03:00:00Z")
        self.assertEqual(summary["forwardCoverage"]["M15"]["ageAtLastImportSeconds"],310)
        self.assertIs(summary["tradeSignalReady"],False)
        self.assertEqual(summary["researchCandidate"],"NONE")
        self.assertEqual(summary["gapReference"]["status"],
                         "REFERENCE_ONLY_NOT_BROKER_VERIFIED")
        self.assertEqual(summary["gapReference"]["frames"]["M15"]["unclassifiedMissingSlots"],0)
        self.assertFalse(summary["gapReference"]["independentBrokerCalendarVerified"])
        self.assertFalse(summary["gapReference"]["sourceRightsVerified"])
        self.assertFalse(summary["gapReference"]["paperOrdersAllowed"])
        self.assertTrue(summary["gapReference"]["allGapsRemainUnclassified"])
        safe_json=json.dumps(summary)
        for private_key in ('"bid"','"ask"','"open"','"high"','"low"','"close"'):
            self.assertNotIn(private_key,safe_json)
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

    def test_quote_freshness_is_read_only_and_never_broker_entitlement(self):
        # No external requests, no orders, only a known synthetic receipt.
        no_capture=inspect_metadata(self.folder,now_utc=NOW)
        self.assertEqual(no_capture["captureFreshness"]["status"],"NO_CAPTURE")
        self.assertIsNone(no_capture["captureFreshness"]["ageSeconds"])
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            ingest(self.folder,self.s,received_utc=iso(NOW))
            recent=inspect_metadata(self.folder,now_utc=NOW+dt.timedelta(seconds=299))
            cutoff=inspect_metadata(self.folder,now_utc=NOW+dt.timedelta(seconds=300))
            stale=inspect_metadata(self.folder,now_utc=NOW+dt.timedelta(seconds=301))
            future=inspect_metadata(self.folder,now_utc=NOW-dt.timedelta(seconds=1))
        self.assertEqual(recent["captureFreshness"]["status"],"RECENT_UNVERIFIED")
        self.assertEqual(cutoff["captureFreshness"]["status"],"RECENT_UNVERIFIED")
        self.assertEqual(stale["captureFreshness"]["status"],"STALE_OVER_5_MINUTES")
        self.assertEqual(stale["captureFreshness"]["ageSeconds"],301)
        self.assertEqual(future["captureFreshness"]["status"],
                         "FUTURE_CAPTURE_OR_CLOCK_SKEW")
        self.assertIsNone(future["captureFreshness"]["ageSeconds"])
        self.assertEqual(
            capture_freshness(iso(NOW),1,now_utc=dt.datetime(2026,11,19)),
            {**capture_freshness(None,0,now_utc=dt.datetime(2026,11,19)),
             "status":"UTC_CLOCK_UNVERIFIED"})
        for report in (no_capture,recent,cutoff,stale,future):
            f=report["captureFreshness"]
            self.assertEqual(f["signal"],"WAIT")
            self.assertFalse(f["sourceQualified"])
            self.assertFalse(f["brokerCalendarVerified"])
            self.assertFalse(f["captureVerifiedByBroker"])
            self.assertFalse(f["paperOrdersAllowed"])
            self.assertFalse(f["executable"])
            self.assertEqual(report["tradeSignalReady"],False)
            safe=json.dumps(f)
            for secret in ('"bid"','"ask"','"spread"','"close"'):
                self.assertNotIn(secret,safe)
        self.assertEqual(len(load_vault(self.folder)["quoteObservations"]),1)

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
        # A candle within the last fully CLOSED 20:00–00:00 H4 bar,
        # not the 00:00–04:00 H4 currently forming at NOW=03:05 UTC.
        altered["frames"]["M15"]["bars"].pop(18)
        r=ingest(self.folder,altered,received_utc=iso(NOW))
        self.safe(r)
        self.assertGreater(r["crossFrameIncompleteM15"]["H1"],0)
        self.assertGreater(r["crossFrameIncompleteM15"]["H4"],0)
        rows=load_vault(self.folder)["closed"]["M15"]
        self.assertEqual(len(rows),r["totals"]["M15"])
        coverage=inspect_metadata(self.folder)["forwardCoverage"]["M15"]
        self.assertEqual(coverage["unclassifiedGapPairs"],1)
        self.assertEqual(coverage["unclassifiedMissingSlots"],1)
        summary=inspect_metadata(self.folder)
        self.assertEqual(summary["gapReference"]["frames"]["M15"]["unclassifiedMissingSlots"],1)
        self.assertEqual(summary["gapReference"]["frames"]["M15"]["outsideVendorReferenceSlots"],0)
        self.assertEqual(summary["gapReference"]["frames"]["M15"]["vendorPauseCandidateSlotsNotVerified"],1)
        self.assertFalse(summary["gapReference"]["independentBrokerCalendarVerified"])
        self.assertLess(coverage["latestContiguousBars"],coverage["closedBars"])
        self.assertEqual(r["status"],"PRIVATE_FORWARD_CAPTURE_SAVED")

    def test_partial_h4_price_contradiction_cannot_be_written_to_vault(self):
        altered=copy.deepcopy(self.s)
        # Exercise the real 20:00-00:00 H4 within the new test holdout;
        # missing one 22:15 M15 may be a reference pause but no gap can
        # excuse a high less than an OBSERVED same-feed M15 high.
        missing="2026-11-18T22:15:00Z"
        altered["frames"]["M15"]["bars"]=[
            item for item in altered["frames"]["M15"]["bars"]
            if item["openTime"]!=missing]
        h4=next(item for item in altered["frames"]["H4"]["bars"]
                if item["openTime"]=="2026-11-18T20:00:00Z")
        h4["high"]=max(h4["open"],h4["close"])+0.01
        with patch.object(socket,"socket",side_effect=AssertionError("NETWORK_NOT_ALLOWED")):
            with self.assertRaisesRegex(
                    ValueError,"PARTIAL_CROSS_FRAME_OBSERVED_PRICE_BOUNDS_INVALID"):
                ingest(self.folder,altered,received_utc=iso(NOW))
        self.assertFalse((self.folder/FILE).exists())
        self.assertEqual(inspect_metadata(self.folder)["counts"]["H4"],0)

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
