"""Synthetic-only isolated backup restore; no network, pricing or orders."""
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from biquote_private_forward_vault import FILE, ingest, load_vault
from biquote_collector_restore_rehearsal import rehearse_restore
from test_biquote_private_forward_vault import NOW, iso, sample

class RestoreRehearsal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gpp-restore-tests-")
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / "source"
        self.backup = self.root / "backup"
        self.source.mkdir(mode=0o700)
        self.backup.mkdir(mode=0o700)
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            ingest(self.source, sample(NOW), received_utc=iso(NOW))
        shutil.copyfile(self.source / FILE, self.backup / FILE)
        os.chmod(self.backup / FILE, 0o600)
    def tearDown(self):
        self.temp.cleanup()
    def assertSafe(self, result):
        self.assertEqual(result["signal"], "WAIT")
        for k in ("executable", "paperOrdersAllowed", "liveOrdersAllowed",
                  "deployApproved", "collectorRestartApproved",
                  "independentBackupVerified", "cloudBackupRecoverabilityVerified",
                  "strategyProfitabilityProven"):
            self.assertFalse(result[k], k)
        self.assertEqual(result["providerRequestsMade"], 0)
        self.assertEqual(result["collectorArchiveWrites"], 0)
        self.assertEqual(result["backupArchiveWrites"], 0)
        rendered = json.dumps(result)
        for private in ('"bid"', '"ask"', '"open"', '"high"', '"low"',
                        '"close"', str(self.source), str(self.backup), '3900.'):
            self.assertNotIn(private, rendered)
    def test_backup_restores_without_live_source_or_extra_calls(self):
        before = (self.backup / FILE).read_bytes()
        self.source.rename(self.root / "source-unavailable")
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            result = rehearse_restore(self.backup, now_utc=NOW)
        self.assertEqual(result["status"],
                         "ISOLATED_LOCAL_RESTORE_PASS_NOT_DEPLOY_APPROVAL")
        self.assertTrue(result["isolatedLocalRestorePassed"])
        self.assertTrue(result["recoveredCopyDestroyedAfterTest"])
        self.assertGreater(result["closedCounts"]["M15"], 0)
        self.assertEqual(result["closedCounts"], result["locallyTimestampedCounts"])
        self.assertEqual(result["legacyUnknownCounts"],
                         {"M15":0, "H1":0, "H4":0})
        self.assertEqual((self.backup / FILE).read_bytes(), before)
        self.assertSafe(result)
    def test_legacy_first_seen_unknown_even_after_full_restore(self):
        stored = load_vault(self.backup)
        stored.pop("firstObservedClosedUTC")
        canonical = json.dumps(stored, sort_keys=True,
                               separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        (self.backup / FILE).write_text(json.dumps(
            {"payload": stored, "sha256": digest}))
        result = rehearse_restore(self.backup, now_utc=NOW)
        self.assertTrue(result["isolatedLocalRestorePassed"])
        self.assertEqual(result["locallyTimestampedCounts"],
                         {"M15":0, "H1":0, "H4":0})
        self.assertEqual(result["legacyUnknownCounts"], result["closedCounts"])
        self.assertSafe(result)
    def test_missing_corrupted_permission_and_symlink_are_blocked(self):
        before = (self.backup / FILE).read_bytes()
        self.assertEqual(rehearse_restore(self.root / "missing", now_utc=NOW)
                         ["status"], "BLOCKED")
        try:
            (self.backup / FILE).write_bytes(before[:70])
            self.assertEqual(rehearse_restore(self.backup, now_utc=NOW)
                             ["status"], "BLOCKED")
            (self.backup / FILE).write_bytes(before)
            os.chmod(self.backup / FILE, 0o644)
            self.assertEqual(rehearse_restore(self.backup, now_utc=NOW)
                             ["status"], "BLOCKED")
        finally:
            (self.backup / FILE).write_bytes(before)
            os.chmod(self.backup / FILE, 0o600)
        (self.backup / FILE).unlink()
        (self.backup / FILE).symlink_to(self.source / FILE)
        result = rehearse_restore(self.backup, now_utc=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertSafe(result)
    def test_invalid_clock_and_missing_receipt_fail_closed(self):
        result = rehearse_restore(self.backup, now_utc=dt.datetime(2026, 11, 19))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertSafe(result)

if __name__ == "__main__":
    unittest.main()
