"""Offline WAL-safe synthetic paper backup/restore drills.

No paid volume, Render mutations, vendor requests, real accounts or orders.
All files live in TemporaryDirectory and are deleted after the test.
"""
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from offline_paper_outcome_journal import OfflineJournal
from offline_paper_snapshot_recovery import snapshot, restore
from test_offline_paper_outcome_journal import event, close, stamp


class BackupAndRestartRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.original = root / "original.sqlite3"
        self.backup = root / "checkpoint.sqlite3"
        self.manifest = root / "checkpoint.json"
        self.restored = root / "recovered.sqlite3"
        self.j = OfflineJournal(self.original)
        self.assertEqual(self.j.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def tearDown(self):
        self.j.close()

    def populate(self):
        self.j.append(event("wait1", 1, "WAIT"))
        self.j.append(event("outage1", 2, "SOURCE_BLOCKED"))
        self.j.append(event("closed1", 92, "PAPER_CLOSED", close(1, 2)))

    def test_live_wal_backup_then_reboot_preserves_events_and_costs(self):
        self.populate()
        before = self.j.summary()
        result = snapshot(self.original, self.backup, self.manifest)
        self.assertEqual(result["status"], "LOCAL_SNAPSHOT_VERIFIED_OFFSITE_NOT_ATTESTED")
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["closedTrades"], 1)
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        meta = json.loads(self.manifest.read_text())
        self.assertEqual(meta["rows"], 3)
        self.assertFalse(meta["externallyDurableOrReplicated"])
        self.assertFalse(meta["independentHoldoutValidated"])
        self.assertFalse(meta["marketDataOrTradingEnabled"])
        self.assertEqual(meta["headDigest"], before["lastDigest"])
        self.assertTrue(self.backup.is_file())
        self.assertEqual(self.backup.stat().st_mode & 0o077, 0)
        # A live writer may safely continue AFTER the snapshot.
        self.j.append(event("newer", 93, "WAIT"))
        self.assertEqual(self.j.summary()["rows"], 4)
        outcome = restore(self.backup, self.manifest, self.restored)
        self.assertEqual(outcome["status"], "OFFLINE_SYNTHETIC_JOURNAL_RESTORED")
        self.assertEqual(outcome["rows"], 3)
        self.assertEqual(outcome["headDigest"], before["lastDigest"])
        repaired = OfflineJournal(self.restored)
        try:
            self.assertEqual(repaired.summary(), before)
            self.assertEqual(repaired.append(event("wait1", 1, "WAIT")),
                             {"duplicate": True, "recorded": False})
            self.assertEqual(repaired.append(event("newer", 93, "WAIT")),
                             {"duplicate": False, "recorded": True})
            self.assertEqual(repaired.summary()["closedPaperTrades"], 1)
            self.assertEqual(repaired.summary()["signal"], "WAIT")
            self.assertEqual(repaired.summary()["brokerOrdersSent"], 0)
            self.assertEqual(repaired.db.execute(
                "PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            repaired.close()

    def test_empty_journal_backup_restores_wait_and_same_frozen_identity(self):
        saved = self.j.summary()
        snapshot(self.original, self.backup, self.manifest)
        restore(self.backup, self.manifest, self.restored)
        opened = OfflineJournal(self.restored)
        try:
            self.assertEqual(opened.summary(), saved)
            self.assertEqual(opened.summary()["closedPaperTrades"], 0)
            self.assertIsNone(opened.summary()["modeledNetUsd"])
        finally:
            opened.close()
        with self.assertRaises(ValueError):
            OfflineJournal(self.restored, freeze_utc=stamp(1))

    def test_refuses_existing_destinations_and_never_overwrites(self):
        self.populate()
        snapshot(self.original, self.backup, self.manifest)
        previous_hash = self.backup.read_bytes()
        previous_manifest = self.manifest.read_bytes()
        with self.assertRaises(ValueError):
            snapshot(self.original, self.backup, self.manifest)
        self.assertEqual(self.backup.read_bytes(), previous_hash)
        self.assertEqual(self.manifest.read_bytes(), previous_manifest)
        self.restored.write_bytes(b"DO_NOT_OVERWRITE")
        with self.assertRaises(ValueError):
            restore(self.backup, self.manifest, self.restored)
        self.assertEqual(self.restored.read_bytes(), b"DO_NOT_OVERWRITE")

    def test_corrupt_backup_and_manifest_fail_before_restore(self):
        self.populate()
        snapshot(self.original, self.backup, self.manifest)
        data = bytearray(self.backup.read_bytes())
        data[300] ^= 0x01
        self.backup.write_bytes(data)
        with self.assertRaises(ValueError):
            restore(self.backup, self.manifest, self.restored)
        self.assertFalse(self.restored.exists())
        # Restoring a healthy backup with a forged row count must fail.
        self.backup.unlink()
        self.manifest.unlink()
        snapshot(self.original, self.backup, self.manifest)
        m = json.loads(self.manifest.read_text())
        m["rows"] += 1
        self.manifest.write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            restore(self.backup, self.manifest, self.restored)
        self.assertFalse(self.restored.exists())

    def test_damaged_source_chain_or_schema_never_backup(self):
        self.populate()
        self.j.db.execute("DROP TRIGGER no_journal_update")
        with self.assertRaises(ValueError):
            snapshot(self.original, self.backup, self.manifest)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.manifest.exists())

    def test_missing_files_symlink_or_relative_paths_refused(self):
        with self.assertRaises(ValueError):
            restore(self.backup, self.manifest, self.restored)
        with self.assertRaises(ValueError):
            snapshot("relative.sqlite3", self.backup, self.manifest)
        link = self.original.parent / "alias.sqlite3"
        link.symlink_to(self.original)
        with self.assertRaises(ValueError):
            snapshot(link, self.backup, self.manifest)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.manifest.exists())


    def test_directory_sync_failure_rolls_back_both_new_snapshot_outputs(self):
        self.populate()
        before = self.j.summary()
        with patch("offline_paper_snapshot_recovery._fsync_dir",
                   side_effect=OSError("simulated storage sync failure")):
            with self.assertRaises(OSError):
                snapshot(self.original, self.backup, self.manifest)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(self.j.summary(), before)
        snapshot(self.original, self.backup, self.manifest)
        self.assertTrue(self.backup.exists())
        self.assertTrue(self.manifest.exists())

    def test_restore_sync_failure_leaves_no_unverified_destination(self):
        self.populate()
        before = self.j.summary()
        snapshot(self.original, self.backup, self.manifest)
        with patch("offline_paper_snapshot_recovery._fsync_dir",
                   side_effect=OSError("simulated restore sync failure")):
            with self.assertRaises(OSError):
                restore(self.backup, self.manifest, self.restored)
        self.assertFalse(self.restored.exists())
        self.assertTrue(self.backup.exists())
        self.assertTrue(self.manifest.exists())
        self.assertEqual(self.j.summary(), before)
        result = restore(self.backup, self.manifest, self.restored)
        self.assertEqual(result["rows"], before["rows"])


if __name__ == "__main__":
    unittest.main()
