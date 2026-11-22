"""Offline private BiQuote predeploy vault gate: never interprets logs as backup."""
import datetime as dt
import json
import os
import pathlib
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import FILE, ingest
from biquote_private_archive_predeploy_guard import preflight
from test_biquote_private_forward_vault import NOW, iso, sample


class ArchivePredeployGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="private-backup-gate-")
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.source = root / "source"
        self.backup = root / "backup"
        self.source.mkdir(mode=0o700)
        self.backup.mkdir(mode=0o700)
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            ingest(self.source, sample(NOW), received_utc=iso(NOW))
        shutil.copyfile(self.source / FILE, self.backup / FILE)
        os.chmod(self.backup / FILE, 0o600)

    def assert_safe(self, result):
        self.assertEqual(result["mode"], "GOLD_PRIVATE_ARCHIVE_PREDEPLOY_READ_ONLY_V1")
        self.assertFalse(result["reviewDeployApproved"])
        self.assertFalse(result["coordinatorRestartApproved"])
        self.assertFalse(result["rawPriceExported"])
        self.assertFalse(result["sourceDataTradingEligible"])
        self.assertFalse(result["independentBrokerRightsVerified"])
        self.assertEqual(result["providerRequestsMade"], 0)
        self.assertEqual(result["brokerOrdersSent"], 0)
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        rendered = json.dumps(result)
        for secret in ['"bid"', '"ask"', '"open"', '"close"', "3900.",
                       str(self.source), str(self.backup), "api_key"]:
            self.assertNotIn(secret, rendered)

    def test_missing_real_archive_not_inferred_from_render_logs(self):
        for params in [
            {},
            {"source_dir": str(self.source)},
            {"source_dir": str(self.source), "backup_dir": str(self.backup),
             "now_utc": dt.datetime(2026, 11, 22)},
            {"source_dir": str(self.source), "backup_dir": str(self.source),
             "now_utc": NOW},
        ]:
            report = preflight(**params)
            self.assert_safe(report)
            self.assertEqual(report["status"],
                             "BLOCKED_UNTIL_OWNER_BACKUP_EVIDENCE")
            self.assertFalse(report["exactBackupBytesVerified"])

    def test_matched_on_same_ephemeral_disk_still_blocks_deploy(self):
        before = (self.source / FILE).read_bytes(), (self.backup / FILE).read_bytes()
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            report = preflight(self.source, self.backup, now_utc=NOW)
        self.assert_safe(report)
        self.assertEqual(report["reason"], "BACKUP_SAME_DEVICE_OR_NOT_INDEPENDENT")
        self.assertFalse(report["independentStorageDeviceVerified"])
        self.assertEqual(before, ((self.source / FILE).read_bytes(),
                                 (self.backup / FILE).read_bytes()))

    def test_corrupt_sealed_copy_and_missing_source_fail_closed(self):
        original = (self.backup / FILE).read_bytes()
        (self.backup / FILE).write_bytes(original[:60])
        self.assert_safe(preflight(self.source, self.backup, now_utc=NOW))
        (self.backup / FILE).unlink()
        self.assert_safe(preflight(self.source, self.backup, now_utc=NOW))
        self.assert_safe(preflight(self.source, self.source.parent / "unknown",
                                   now_utc=NOW))

    def test_even_mocked_separate_device_and_restore_does_not_approve_deploy(self):
        base = {
            "status": "LOCAL_MATCH_NO_DEPLOY_APPROVAL",
            "exactSealedBytesMatch": True,
            "sameDeviceDetected": False,
            "sourceRightsVerified": False,
            "deployApproved": False,
            "sourceClosedCounts": {"M15": 1, "H1": 1, "H4": 1}
        }
        recovery = {
            "status": "ISOLATED_LOCAL_RESTORE_PASS_NOT_DEPLOY_APPROVAL",
            "isolatedLocalRestorePassed": True,
            "recoveredCopyDestroyedAfterTest": True,
            "sourceRightsVerified": False,
            "brokerCalendarVerified": False,
            "closedCounts": {"M15": 1, "H1": 1, "H4": 1},
            "quoteObservationCount": 3,
        }
        with patch("biquote_private_archive_predeploy_guard.review",
                   return_value=base), patch(
                       "biquote_private_archive_predeploy_guard.rehearse_restore",
                       return_value=recovery):
            result = preflight(self.source, self.backup, now_utc=NOW)
            self.assert_safe(result)
            self.assertEqual(result["status"],
                             "LOCAL_DIFFERENT_DEVICE_RESTORE_ONLY")
            self.assertTrue(result["isolatedRestorePassed"])
            self.assertEqual(result["sourceClosedCounts"]["M15"], 1)
            self.assertFalse(result["reviewDeployApproved"])
        for delta in [
            {**recovery, "closedCounts": {"M15": 2, "H1": 1, "H4": 1}},
            {**recovery, "sourceRightsVerified": True},
            {**recovery, "isolatedRestorePassed": False},
        ]:
            with patch("biquote_private_archive_predeploy_guard.review",
                       return_value=base), patch(
                           "biquote_private_archive_predeploy_guard.rehearse_restore",
                           return_value=delta):
                bad = preflight(self.source, self.backup, now_utc=NOW)
                self.assert_safe(bad)
                self.assertEqual(bad["status"],
                                 "BLOCKED_UNTIL_OWNER_BACKUP_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
