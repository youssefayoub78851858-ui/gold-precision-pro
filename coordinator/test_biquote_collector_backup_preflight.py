"""No-network synthetic local backup rehearsal."""
import datetime as dt
import os
import pathlib
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch
from biquote_collector_backup_preflight import review,END
from biquote_private_forward_vault import FILE,ingest
from test_biquote_private_forward_vault import NOW,iso,sample

class BackupPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="gpp-backup-check-")
        root=pathlib.Path(self.tmp.name)
        self.a,self.b=root/"original",root/"copy"
        self.a.mkdir(mode=0o700)
        self.b.mkdir(mode=0o700)
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            ingest(self.a,sample(NOW),received_utc=iso(NOW))
        shutil.copyfile(self.a/FILE,self.b/FILE)
        os.chmod(self.b/FILE,0o600)
    def tearDown(self): self.tmp.cleanup()
    def test_matched_local_copy_still_never_approves_deploy(self):
        before=(self.a/FILE).read_bytes(),(self.b/FILE).read_bytes()
        for clock,finished,expected in [
            (NOW,False,"ACTIVE_CAPTURE_DO_NOT_RESTART"),
            (END+dt.timedelta(seconds=1),False,"FINAL_CAPTURE_PROOF_REQUIRED"),
            (END+dt.timedelta(seconds=1),True,"EXTERNAL_RECOVERY_EVIDENCE_REQUIRED")]:
            with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
                out=review(self.a,self.b,now_utc=clock,finished=finished)
            self.assertEqual(out["reason"],expected)
            self.assertEqual(out["status"],"LOCAL_MATCH_NO_DEPLOY_APPROVAL")
            self.assertTrue(out["exactSealedBytesMatch"])
            self.assertTrue(out["sameDeviceDetected"])
            self.assertEqual(out["signal"],"WAIT")
            for key in ("deployApproved","collectorRestartApproved","archiveRecoveryProven",
                        "independentOffsiteBackupVerified","paperOrdersAllowed",
                        "liveOrdersAllowed"):
                self.assertFalse(out[key])
            self.assertEqual(out["archiveWriteOperations"],0)
            self.assertNotIn("3900.",str(out))
            self.assertNotIn(str(self.a),str(out))
        self.assertEqual(before,((self.a/FILE).read_bytes(),(self.b/FILE).read_bytes()))
    def test_missing_corruption_and_stale_backup_block(self):
        self.assertEqual(review(self.a,self.a,now_utc=NOW)["status"],"BLOCKED")
        self.assertEqual(review(self.a,self.b.parent/"missing",now_utc=NOW)["status"],"BLOCKED")
        intact=(self.b/FILE).read_bytes()
        try:
            (self.b/FILE).write_bytes(intact[:40])
            self.assertEqual(review(self.a,self.b,now_utc=NOW)["status"],"BLOCKED")
            (self.b/FILE).write_bytes(intact)
            os.chmod(self.b/FILE,0o644)
            self.assertEqual(review(self.a,self.b,now_utc=NOW)["reason"],
                             "INSECURE_SNAPSHOT_PERMISSIONS")
        finally:
            (self.b/FILE).write_bytes(intact)
            os.chmod(self.b/FILE,0o600)
        later=NOW+dt.timedelta(minutes=17)
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            ingest(self.a,sample(later),received_utc=iso(later))
        self.assertEqual(review(self.a,self.b,now_utc=later)["reason"],
                         "BACKUP_COUNTERS_MISMATCH")
    def test_rejects_untrusted_time_and_status(self):
        self.assertEqual(review(self.a,self.b,now_utc=dt.datetime(2026,11,19))["status"],"BLOCKED")
        self.assertEqual(review(self.a,self.b,now_utc=NOW,finished="yes")["status"],"BLOCKED")

if __name__=="__main__":unittest.main()
