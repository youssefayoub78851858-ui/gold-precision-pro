"""Sealed archive -> local V3 replay, synthetic only and no network."""
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import ingest,load_vault
from biquote_v3_chronological_private import inspect_private_vault
from test_biquote_forward_shadow_review import AFTER
from test_biquote_private_forward_vault import sample,iso

class ChronologicalPrivate(unittest.TestCase):
    def test_sealed_archive_count_only_no_private_prices_or_disk_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=pathlib.Path(tmp)/"private"
            with patch.object(socket,"socket",side_effect=AssertionError("NO_EXTERNAL_NETWORK")):
                ingest(directory,sample(AFTER),received_utc=iso(AFTER))
                stored=load_vault(directory)
                before=(directory/"biquote-forward-private-v1.json").read_bytes()
                report=inspect_private_vault(directory)
                after=(directory/"biquote-forward-private-v1.json").read_bytes()
            self.assertEqual(before,after)
            self.assertEqual(report["mode"],
                             "BIQUOTE_V3_PRIVATE_CHRONOLOGICAL_REPLAY_COUNTS_ONLY")
            self.assertEqual(report["signal"],"WAIT")
            self.assertFalse(report["executable"])
            self.assertFalse(report["paperOrdersAllowed"])
            self.assertFalse(report["liveOrdersAllowed"])
            self.assertFalse(report["sourceRightsVerified"])
            self.assertFalse(report["firstAvailablePerCandleVerified"])
            self.assertIsNone(report["netExpectancy"])
            self.assertIsNone(report["costAdjustedPnL"])
            self.assertEqual(report["closedCounts"],
                {k:len(v) for k,v in stored["closed"].items()})
            self.assertEqual(report["retrospectiveDecisionCount"],
                             sum(report["technicalWatchCounts"].values()))
            gate=report["pointInTimeDataAudit"]
            self.assertEqual(gate["signal"],"WAIT")
            self.assertFalse(gate["sourceRightsVerified"])
            self.assertFalse(gate["independentAvailabilityVerified"])
            self.assertFalse(gate["brokerSessionCalendarVerified"])
            self.assertEqual(gate["observedAtDecision"],{
                tf:len(stored["firstObservedClosedUTC"][tf])
                for tf in ("M15","H1","H4")})
            self.assertEqual(gate["legacyWithoutFirstSeen"],
                             {"M15":0,"H1":0,"H4":0})
            for tf in ("M15","H1","H4"):
                contiguous=gate["contiguousObservedClosed"][tf]
                self.assertLessEqual(contiguous,gate["observedAtDecision"][tf])
                self.assertEqual(gate["technicalWarmupMissing"][tf],
                                 max(0,21-contiguous))
                self.assertEqual(gate["paperHistoryMissing"][tf],
                                 max(0,50-contiguous))
            receipts=report["localFirstSeenAudit"]
            self.assertEqual(receipts["signal"],"WAIT")
            self.assertFalse(receipts["paperOrdersAllowed"])
            self.assertFalse(receipts["independentReceiptVerified"])
            self.assertEqual(receipts["recordedClosedCounts"],
                {tf:len(stored["firstObservedClosedUTC"][tf])
                 for tf in ("M15","H1","H4")})
            self.assertEqual(receipts["unknownLegacyClosedCounts"],
                             {"M15":0,"H1":0,"H4":0})
            self.assertEqual(receipts["observedDecisionCount"],
                             sum(receipts["technicalWatchCounts"].values()))
            self.assertLessEqual(receipts["observedDecisionCount"],256)
            safe=json.dumps(report)
            for private in ('"open"','"high"','"low"','"close"',
                            '"bid"','"ask"','3900.0','/private'):
                self.assertNotIn(private,safe)
            self.assertFalse(any(x.suffix in (".db",".sqlite",".sqlite3")
                                 for x in directory.rglob("*")))
            # Tampered runner claims must not be passed to authenticated UI.
            forged=inspect_private_vault(directory,runner=lambda packet:
                json.dumps({**json.loads(
                    __import__("subprocess").run(
                        ["node",str(pathlib.Path(__file__).with_name(
                            "biquote_v3_chronological_replay.js"))],
                        input=json.dumps(packet),capture_output=True,
                        text=True,check=True).stdout),
                    "signalDataReadiness":{"status":"LOCAL_GEOMETRY_ONLY_NOT_TRADE_READY",
                                           "signal":"BUY"}}))
            self.assertEqual(forged["status"],"BLOCKED")
            self.assertNotIn("pointInTimeDataAudit",forged)
            # A compromised runner cannot assert success, leak pricing,
            # promote orders, or fake a first-seen market replay.
            fake={**report,"status":"RETROSPECTIVE_WATCH_COUNTS_ONLY",
                 "sourceRightsVerified":True,"signal":"BUY"}
            blocked=inspect_private_vault(directory,
                       runner=lambda _ : json.dumps(fake))
            self.assertEqual(blocked["status"],"BLOCKED")
            self.assertEqual(blocked["retrospectiveDecisionCount"],0)
            self.assertNotIn('"bid"',json.dumps(blocked))
    def test_legacy_archive_does_not_fake_receipts_or_future_observations(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            directory=pathlib.Path(tmp)/"private"
            ingest(directory,sample(AFTER),received_utc=iso(AFTER))
            old=load_vault(directory)
            old.pop("firstObservedClosedUTC")
            digest=hashlib.sha256(json.dumps(old,sort_keys=True,separators=(",",
                          ":"),ensure_ascii=True).encode()).hexdigest()
            archive=directory/"biquote-forward-private-v1.json"
            archive.write_text(json.dumps({"payload":old,"sha256":digest}))
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
                report=inspect_private_vault(directory)
            audit=report["localFirstSeenAudit"]
            self.assertEqual(audit["status"],"BLOCKED")
            self.assertEqual(audit["observedDecisionCount"],0)
            self.assertEqual(audit["recordedClosedCounts"],{
                "M15":0,"H1":0,"H4":0})
            self.assertEqual(audit["unknownLegacyClosedCounts"],{
                tf:len(old["closed"][tf]) for tf in ("M15","H1","H4")})
            self.assertEqual(report["signal"],"WAIT")
            self.assertFalse(report["paperOrdersAllowed"])
            gated=report["pointInTimeDataAudit"]
            self.assertEqual(gated["status"],"RECEIPTS_UNAVAILABLE")
            self.assertEqual(gated["observedAtDecision"],{"M15":0,"H1":0,"H4":0})
            self.assertEqual(gated["legacyWithoutFirstSeen"],{
                tf:len(old["closed"][tf]) for tf in ("M15","H1","H4")})
            # Legacy timestamps are never manufactured using the last import.
            self.assertEqual(gated["contiguousObservedClosed"],{
                "M15":0,"H1":0,"H4":0})

    def test_missing_vault_does_not_generate_market_candles(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=pathlib.Path(tmp)/"missing"
            o=inspect_private_vault(d,runner=lambda _ : json.dumps({}))
            self.assertEqual(o["signal"],"WAIT")
            self.assertEqual(o["status"],"BLOCKED")
            self.assertEqual(o["retrospectiveDecisionCount"],0)
            self.assertFalse(d.exists())

if __name__=="__main__":
    unittest.main()
