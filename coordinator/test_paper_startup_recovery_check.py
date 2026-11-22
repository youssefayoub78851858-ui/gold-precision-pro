"""Startup journal checkpoint proof: valid append-only ancestry only.

Tests are all temporary offline synthetic journals. No provider, mounted
disk, background service, account token or real trading.
"""
import json
import pathlib
import tempfile
import unittest

from offline_paper_outcome_journal import OfflineJournal
from offline_paper_snapshot_recovery import snapshot
from paper_startup_recovery_check import attest
from test_offline_paper_outcome_journal import event, close, stamp


class PaperStartupRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.live = root / "live.sqlite3"
        self.backup = root / "saved.sqlite3"
        self.manifest = root / "saved.json"
        self.db = OfflineJournal(self.live)

    def tearDown(self):
        self.db.close()

    def add_one(self):
        self.db.append(event("wait", 1, "WAIT"))
        self.db.append(event("trade", 92, "PAPER_CLOSED", close(1, 2)))

    def test_existing_snapshot_prefix_survives_reboot_and_more_events(self):
        self.add_one()
        snapshot(self.live, self.backup, self.manifest)
        initial = attest(self.live, self.backup, self.manifest)
        self.assertEqual(initial["status"],
                         "LOCAL_JOURNAL_CHECKPOINT_ANCESTRY_VERIFIED")
        self.assertEqual(initial["journalRows"], 2)
        self.assertEqual(initial["closedPaperTrades"], 1)
        self.assertIs(initial["externallyDurableOrReplicated"], False)
        self.assertEqual(initial["signal"], "WAIT")
        self.assertIs(initial["executable"], False)
        self.db.append(event("later", 93, "SOURCE_BLOCKED"))
        newer = attest(self.live, self.backup, self.manifest)
        self.assertEqual(newer["journalRows"], 3)
        self.assertEqual(newer["checkpointRows"], 2)
        self.assertEqual(newer["closedPaperTrades"], 1)
        self.db.close()
        self.db = OfflineJournal(self.live)
        self.assertEqual(attest(self.live, self.backup, self.manifest), newer)
        self.assertEqual(self.db.append(event("later", 93, "SOURCE_BLOCKED")),
                         {"duplicate": True, "recorded": False})

    def test_missing_manifest_and_snapshot_do_not_create_files(self):
        self.add_one()
        with self.assertRaises(ValueError):
            attest(self.live, self.backup, self.manifest)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.manifest.exists())

    def test_reject_rollback_to_stale_live_journal(self):
        self.add_one()
        snapshot(self.live, self.backup, self.manifest)
        # Restore an earlier empty live ledger as a distinct file.
        old = self.live.parent / "old.sqlite3"
        other = OfflineJournal(old)
        other.close()
        with self.assertRaises(ValueError):
            attest(old, self.backup, self.manifest)

    def test_reject_diverging_hash_chain_with_same_row_count(self):
        self.add_one()
        snapshot(self.live, self.backup, self.manifest)
        alternate = self.live.parent / "alternate.sqlite3"
        other = OfflineJournal(alternate)
        try:
            other.append(event("different", 1, "WAIT"))
            other.append(event("trade", 92, "PAPER_CLOSED", close(1, 2)))
        finally:
            other.close()
        with self.assertRaises(ValueError):
            attest(alternate, self.backup, self.manifest)

    def test_reject_invalid_source_triggers_manifest_or_bytes(self):
        self.add_one()
        snapshot(self.live, self.backup, self.manifest)
        obj = json.loads(self.manifest.read_text())
        obj["closedTrades"] = 999
        self.manifest.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            attest(self.live, self.backup, self.manifest)
        # Recreate the original manifest only to test byte tampering.
        self.manifest.unlink()
        self.backup.unlink()
        snapshot(self.live, self.backup, self.manifest)
        content = bytearray(self.backup.read_bytes())
        content[256] ^= 1
        self.backup.write_bytes(content)
        with self.assertRaises(ValueError):
            attest(self.live, self.backup, self.manifest)

    def test_reject_inconsistent_freeze_even_when_events_match(self):
        self.add_one()
        snapshot(self.live, self.backup, self.manifest)
        alternative = self.live.parent / "new-epoch.sqlite3"
        new = OfflineJournal(alternative, freeze_utc="2026-11-18T00:00:30Z")
        try:
            new.append(event("wait", 1, "WAIT"))
            new.append(event("trade", 92, "PAPER_CLOSED", close(1, 2)))
        finally:
            new.close()
        with self.assertRaises(ValueError):
            attest(alternative, self.backup, self.manifest)


if __name__ == "__main__":
    unittest.main()
