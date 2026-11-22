"""One complete OFFLINE test of the dormant paper storage integration.

Bootstraps a new journal in a temporary directory (NOT a Render disk),
proves an empty checkpoint, uses a MOCKED synthetic-only startup gate to
record events, handles an outage/gap, restarts without duplication, validates
the private read-only outcome report, snapshots WAL, restores, and refuses
checkpoint rollback or corrupt files.

The mock gate is NOT proof of mounted storage, broker data, rights, readiness
for production, or anything beyond this isolated CI contract.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from paper_fresh_volume_init import prepare
from paper_startup_recovery_check import attest
from offline_paper_outcome_journal import OfflineJournal
from offline_paper_safe_recorder import record
from offline_paper_report_readonly import inspect
from offline_paper_snapshot_recovery import snapshot, restore
from test_offline_paper_safe_recorder import gate, packet
from test_offline_paper_outcome_journal import close


class IsolatedPaperDeploymentDressRehearsal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.db = root / "simulated.sqlite3"
        self.initial = root / "initial.sqlite3"
        self.initial_meta = root / "initial.json"
        self.snapshot = root / "after-events.sqlite3"
        self.snapshot_meta = root / "after-events.json"
        self.recovered = root / "recovered.sqlite3"
        self.rolled_back = root / "rolled-back.sqlite3"

    def test_full_boot_record_outage_restart_report_backup_restore(self):
        result = prepare(str(self.db.parent), self.db.name,
                         self.initial.name, self.initial_meta.name)
        self.assertEqual(result["status"], "EMPTY_SYNTHETIC_LEDGER_CHECKPOINT_PREPARED")
        self.assertFalse(result["paperAutoRecordingEnabled"])
        self.assertFalse(result["dataSourceLicensed"])
        self.assertEqual(attest(self.db, self.initial, self.initial_meta)["journalRows"], 0)
        self.assertEqual(inspect(str(self.db))["journalRows"], 0)

        with OfflineJournalContext(self.db) as journal:
            # Simulate a prohibited activation when no storage checkpoint
            # is accepted. This MUST not write even a WAIT event.
            with self.assertRaises(ValueError):
                record(journal, None, packet("blocked", 89))
            self.assertEqual(journal.summary()["rows"], 0)
            mock_gate = gate()  # isolated synthetic test, NOT actual disk attestation
            for ident, minute in (("m15_a", 89), ("m15_b", 90)):
                e = record(journal, mock_gate, packet(ident, minute))
                self.assertEqual(e["eventKind"], "WAIT")
                self.assertFalse(e["paperOrdersAllowed"])
                self.assertEqual(e["providerRequestsMade"], 0)
            first_close = packet("paper_close_a", 94, "PAPER_CLOSE", close(1, 2))
            first = record(journal, mock_gate, first_close)
            self.assertEqual(first["eventKind"], "PAPER_CLOSED")
            # A failed source and an >20-minute gap suppress paper-close
            # outcomes until two NEW observations have arrived.
            record(journal, mock_gate, packet("source_down", 96, "SOURCE_DOWN"))
            record(journal, mock_gate, packet("reconnect_a", 97))
            record(journal, mock_gate, packet("reconnect_b", 98))
            late = record(journal, mock_gate,
                          packet("late_close", 153, "PAPER_CLOSE", close(2, -3)))
            self.assertEqual(late["eventKind"], "SOURCE_BLOCKED")
            record(journal, mock_gate, packet("postgap_a", 154))
            record(journal, mock_gate, packet("postgap_b", 155))
            second_close = packet("paper_close_b", 156, "PAPER_CLOSE", close(2, -3))
            self.assertEqual(record(journal, mock_gate, second_close)["eventKind"],
                             "PAPER_CLOSED")
            before = journal.summary()
            self.assertEqual(before["closedPaperTrades"], 2)
            self.assertEqual(before["blockedSourceEvents"], 2)
            self.assertAlmostEqual(before["modeledNetUsd"], -2.2)
            self.assertEqual(before["signal"], "WAIT")
            self.assertFalse(before["executable"])
            self.assertEqual(before["brokerOrdersSent"], 0)
            self.assertFalse(before["realMarketDataConnected"])

        # A clean reboot must recognize both outcomes and exact idempotent
        # replays, without creating any extra order or synthetic trade.
        with OfflineJournalContext(self.db) as rebooted:
            self.assertEqual(rebooted.summary(), before)
            for old in (first_close, second_close):
                replay = record(rebooted, gate(), old)
                self.assertEqual(replay["status"], "DUPLICATE_SKIPPED")
                self.assertFalse(replay["recorded"])
            self.assertEqual(rebooted.summary(), before)
            # Private report reads committed totals; it cannot turn these
            # synthetic records into a next-M15 prediction hit rate.
            report = inspect(str(self.db))
            self.assertEqual(report["cumulative"]["closedTrades"], 2)
            self.assertAlmostEqual(report["cumulative"]["netModeledUsd"], -2.2)
            self.assertIsNone(report["unverifiedNextM15ForecastAccuracy"])
            self.assertFalse(report["realMarketDataConnected"])
            self.assertFalse(report["paperOrderExecutionEnabled"])
            self.assertEqual(report["brokerOrdersSent"], 0)
            for forbidden in ('"side"', '"entryUTC"', '"trade"',
                              "apiKey", "MONITOR_READONLY_TOKEN"):
                self.assertNotIn(forbidden, json.dumps(report))
            current_proof = attest(self.db, self.initial, self.initial_meta)
            self.assertEqual(current_proof["checkpointRows"], 0)
            self.assertEqual(current_proof["journalRows"], before["rows"])

        # The original blank backup is not a replacement for a NEW
        # checkpoint; save the current WAL snapshot before recovery.
        saved = snapshot(self.db, self.snapshot, self.snapshot_meta)
        self.assertEqual(saved["rows"], before["rows"])
        self.assertEqual(saved["closedTrades"], 2)
        self.assertEqual(attest(self.db, self.snapshot, self.snapshot_meta)["checkpointRows"],
                         before["rows"])
        restored = restore(self.snapshot, self.snapshot_meta, self.recovered)
        self.assertEqual(restored["rows"], before["rows"])
        with OfflineJournalContext(self.recovered) as reopened:
            self.assertEqual(reopened.summary(), before)
        self.assertEqual(inspect(str(self.recovered))["cumulative"]["closedTrades"], 2)

        # Rolling the live DB all the way back to its original empty
        # checkpoint must NOT pass the latest post-trade checkpoint.
        restore(self.initial, self.initial_meta, self.rolled_back)
        with self.assertRaises(ValueError):
            attest(self.rolled_back, self.snapshot, self.snapshot_meta)
        with self.assertRaises(ValueError):
            restore(self.snapshot, self.snapshot_meta, self.recovered)

        # Metadata corruption blocks verification, and no live journal
        # data is overwritten.
        meta = json.loads(self.snapshot_meta.read_text())
        meta["closedTrades"] = 999
        self.snapshot_meta.write_text(json.dumps(meta))
        with self.assertRaises(ValueError):
            attest(self.db, self.snapshot, self.snapshot_meta)
        self.assertEqual(inspect(str(self.db))["cumulative"]["closedTrades"], 2)

    def test_no_runtime_files_without_express_storage_bootstrap(self):
        self.assertEqual(list(self.db.parent.iterdir()), [])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.initial.exists())


class OfflineJournalContext:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        self.opened = OfflineJournal(self.path)
        return self.opened
    def __exit__(self, exc_type, exc, traceback):
        self.opened.close()


if __name__ == "__main__":
    unittest.main()
