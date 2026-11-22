"""Existing local volume initialization drill (temp directories ONLY).

Tests local journal and checkpoint bootstrapping, no Render resource creation,
no orders, no provider, no subscription. This is NOT a test of an attached disk.
"""
import pathlib
import tempfile
import unittest

from paper_fresh_volume_init import prepare
from offline_paper_outcome_journal import OfflineJournal
from paper_startup_recovery_check import attest


class FreshSyntheticVolumeInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.journal = self.root / "synthetic-paper.sqlite3"
        self.backup = self.root / "synthetic-checkpoint.sqlite3"
        self.manifest = self.root / "synthetic-checkpoint.json"

    def prepare(self):
        return prepare(str(self.root),
                       self.journal.name,self.backup.name,self.manifest.name)

    def test_prepared_empty_ledger_survives_reopen_and_checkpoint(self):
        report = self.prepare()
        self.assertEqual(report["status"],"EMPTY_SYNTHETIC_LEDGER_CHECKPOINT_PREPARED")
        self.assertEqual(report["journalRows"],0)
        self.assertEqual(report["checkpointRows"],0)
        self.assertFalse(report["paperAutoRecordingEnabled"])
        self.assertFalse(report["externalStorageAndBackupServiceProvisioned"])
        self.assertFalse(report["dataSourceLicensed"])
        self.assertFalse(report["liveMarketDataConnected"])
        self.assertFalse(report["executable"])
        self.assertEqual(report["signal"],"WAIT")
        self.assertEqual(report["brokerOrdersSent"],0)
        self.assertTrue(self.journal.exists())
        self.assertTrue(self.backup.exists())
        self.assertTrue(self.manifest.exists())
        boot = attest(self.journal,self.backup,self.manifest)
        self.assertEqual(boot["status"],"LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED")
        self.assertEqual(boot["journalRows"],0)
        j = OfflineJournal(self.journal)
        try:
            self.assertEqual(j.summary()["rows"],0)
            self.assertEqual(j.summary()["signal"],"WAIT")
            self.assertEqual(j.db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        finally:
            j.close()
        # Never overwrite even with identical configuration.
        with self.assertRaises(ValueError):
            self.prepare()

    def test_partial_or_existing_disk_files_fail_without_overwrite(self):
        self.journal.write_bytes(b"DO_NOT_OVERWRITE")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.journal.read_bytes(),b"DO_NOT_OVERWRITE")
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.manifest.exists())

    def test_invalid_paths_symlinks_and_duplicate_names_fail(self):
        with self.assertRaises(ValueError):
            prepare("relative-path",self.journal.name,
                    self.backup.name,self.manifest.name)
        with self.assertRaises(ValueError):
            prepare(str(self.root),self.journal.name,
                    self.journal.name,self.manifest.name)
        with self.assertRaises(ValueError):
            prepare(str(self.root),"../outside.sqlite3",
                    self.backup.name,self.manifest.name)
        link=self.root.parent/"fake-boot-root-symlink"
        link.symlink_to(self.root,target_is_directory=True)
        try:
            with self.assertRaises(ValueError):
                prepare(str(link),self.journal.name,
                        self.backup.name,self.manifest.name)
        finally:
            link.unlink()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_preexisting_broken_symlink_never_followed(self):
        self.journal.symlink_to(self.root / "missing.sqlite3")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertTrue(self.journal.is_symlink())
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
