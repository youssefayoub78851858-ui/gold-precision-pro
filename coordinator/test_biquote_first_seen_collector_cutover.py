"""Offline restart/migration rehearsal: synthetic data, NO external provider.

A seven-day review worker lives on a Render *single* persistent volume.
A deploy restarts it and may skip one or more polling slots, so the live
collector MUST NOT be redeployed by the existence of this test.
"""
import datetime as dt
import hashlib
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import (
    FILE, ingest, load_vault, inspect_metadata)
from biquote_public_one_shot import ENDPOINTS, one_shot_probe
from test_biquote_private_forward_vault import sample, NOW, iso
from test_biquote_forward_integration import simulated_poll

class CollectorCutoverRehearsal(unittest.TestCase):
    def test_resume_old_archive_no_existing_receipts_backfill_and_only_one_poll(self):
        with tempfile.TemporaryDirectory(prefix="gpp-cutover-test-") as temporary:
            folder=pathlib.Path(temporary)/"archive"
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
                ingest(folder,sample(NOW),received_utc=iso(NOW))
            current=load_vault(folder)
            # Simulate exactly the legacy schema from a running previous image.
            current.pop("firstObservedClosedUTC")
            original_counts={tf:len(current["closed"][tf]) for tf in ("M15","H1","H4")}
            original_rows={tf:list(current["closed"][tf]) for tf in original_counts}
            original_quotes=list(current["quoteObservations"])
            body=json.dumps(current,sort_keys=True,separators=(",",":"),
                            ensure_ascii=True)
            digest=hashlib.sha256(body.encode("utf-8")).hexdigest()
            target=folder/FILE
            target.write_text(json.dumps({"payload":current,"sha256":digest}))
            before=load_vault(folder)
            self.assertNotIn("firstObservedClosedUTC",before)

            # Four hours have elapsed: no catch-up burst, no second source.
            # ONE simulated provider poll, one existing archive sink, and the
            # sealed vault itself retains prior OHLC unchanged.
            later=NOW+dt.timedelta(hours=4)
            fake=sample(later)
            opener,calls=simulated_poll(fake)
            def sink(packet,received):
                return ingest(folder,packet,received_utc=iso(received))
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
                response=one_shot_probe(opener,lambda:later,
                                        private_snapshot_sink=sink)
            self.assertEqual(calls,[uri for _,uri in ENDPOINTS])
            self.assertEqual(response["requestCountAttempted"],4)
            self.assertTrue(response["marketDataStored"])
            self.assertFalse(response["paperOrdersAllowed"])
            self.assertEqual(response["signal"],"WAIT")
            post=load_vault(folder)
            for tf in original_counts:
                old=original_rows[tf]
                self.assertEqual(post["closed"][tf][:len(old)],old)
                stamped=post["firstObservedClosedUTC"][tf]
                self.assertTrue(set(stamped).isdisjoint(
                    {bar["openTime"] for bar in old}))
                self.assertEqual(len(stamped),len(post["closed"][tf])-len(old))
                self.assertTrue(all(t==iso(later) for t in stamped.values()))
            self.assertEqual(post["quoteObservations"][:len(original_quotes)],
                             original_quotes)
            status=inspect_metadata(folder,now_utc=later)
            self.assertEqual(status["firstSeenCoverage"]["unknownLegacyClosed"],
                             original_counts)
            self.assertEqual(status["firstSeenCoverage"]["recordedClosed"],
                             {tf:len(post["closed"][tf])-original_counts[tf]
                              for tf in original_counts})
            self.assertEqual(status["signal"],"WAIT")
            self.assertFalse(status["tradeSignalReady"])
            self.assertFalse(status["paperOrdersAllowed"])
            private_dump=json.dumps(status)
            for secret in ('"bid"','"ask"','"open"','"high"','"low"','"close"'):
                self.assertNotIn(secret,private_dump)
            # Same tick + same bars: no destructive rewrite, no fake new receipt.
            saved=target.read_bytes()
            same=ingest(folder,fake,received_utc=iso(later))
            self.assertEqual(same["status"],"NO_NEW_BARS")
            self.assertEqual(target.read_bytes(),saved)
            # Simulated corrupt incoming quote: fail BEFORE touching disk.
            invalid=sample(later+dt.timedelta(minutes=1))
            invalid["quote"]["stale"]=True
            with self.assertRaises(ValueError):
                ingest(folder,invalid,received_utc=iso(
                    later+dt.timedelta(minutes=1)))
            self.assertEqual(target.read_bytes(),saved)

if __name__=="__main__":
    unittest.main()
