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
    def test_cannot_validate_backup_through_symlinked_ancestor(self):
        alias = self.a.parent / "source-alias"
        alias.symlink_to(self.a, target_is_directory=True)
        # Even if the final file is ordinary, an intermediate symlink
        # must not bypass owner-only private archive identity.
        report = review(alias, self.b, now_utc=NOW)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["exactSealedBytesMatch"])
        self.assertFalse(report["deployApproved"])

    def test_rejects_hardlinks_even_when_identical_bytes(self):
        original = (self.b / FILE).read_bytes()
        (self.b / FILE).unlink()
        os.link(self.a / FILE, self.b / FILE)
        try:
            result = review(self.a, self.b, now_utc=NOW)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["exactSealedBytesMatch"])
            self.assertFalse(result["archiveRecoveryProven"])
        finally:
            (self.b / FILE).unlink()
            (self.b / FILE).write_bytes(original)
            os.chmod(self.b / FILE, 0o600)

    def test_rejects_source_metadata_mutation_during_signed_validation(self):
        from biquote_private_forward_vault import load_vault as actual_load
        first = True

        def mutate_after_read(folder):
            nonlocal first
            result = actual_load(folder)
            if first:
                first = False
                file = self.a / FILE
                stat = file.stat()
                # No data bytes change. An inode metadata race must
                # still fail the predeploy point-in-time validation.
                os.utime(file, ns=(stat.st_atime_ns,
                                   stat.st_mtime_ns + 1_000_000_000))
            return result

        with patch("biquote_collector_backup_preflight.load_vault",
                   side_effect=mutate_after_read):
            checked = review(self.a, self.b, now_utc=NOW)
        self.assertEqual(checked["status"], "BLOCKED")
        self.assertFalse(checked["exactSealedBytesMatch"])
        self.assertFalse(checked["deployApproved"])

    def test_rejects_untrusted_time_and_status(self):
        self.assertEqual(review(self.a,self.b,now_utc=dt.datetime(2026,11,19))["status"],"BLOCKED")
        self.assertEqual(review(self.a,self.b,now_utc=NOW,finished="yes")["status"],"BLOCKED")

if __name__=="__main__":unittest.main()
