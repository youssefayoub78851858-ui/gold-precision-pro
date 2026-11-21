"""Read-only snapshot of an EXISTING local synthetic journal. No providers."""
import os
import pathlib
import tempfile
import unittest
import sqlite3

from offline_paper_outcome_journal import OfflineJournal
from offline_paper_report_readonly import inspect
from test_offline_paper_outcome_journal import event, close


class ReadOnlyPaperViewer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "fixture.sqlite3"
        self.writable = OfflineJournal(self.path)

    def tearDown(self):
        self.writable.close()

    def test_empty_and_frozen_readonly_snapshot(self):
        stat = os.stat(self.path)
        one = inspect(str(self.path))
        self.assertEqual(one["cumulative"]["closedTrades"], 0)
        self.assertEqual(one["signal"], "WAIT")
        self.assertFalse(one["executable"])
        self.assertFalse(one["realMarketDataConnected"])
        self.assertEqual(one["journalRows"], 0)
        self.assertEqual(os.stat(self.path).st_size, stat.st_size)
        self.writable.append(event("wait", 1, "WAIT"))
        self.writable.append(event("trade", 92, "PAPER_CLOSED", close(1, 2)))
        two = inspect(str(self.path))
        self.assertEqual(two["cumulative"]["closedTrades"], 1)
        self.assertAlmostEqual(two["cumulative"]["netModeledUsd"], 1.4)
        self.assertEqual(two["dailyUTC"][0]["waitEvents"], 1)
        self.assertEqual(two["completedFiveTradeBatches"], [])
        self.assertIsNone(two["unverifiedNextM15ForecastAccuracy"])
        self.assertEqual(two["brokerOrdersSent"], 0)
        self.writable.close()
        self.writable = OfflineJournal(self.path)
        self.assertEqual(inspect(str(self.path)), two)

    def test_cannot_create_new_or_accept_symlink(self):
        nofile = pathlib.Path(self.tmp.name) / "missing.sqlite3"
        with self.assertRaises(ValueError):
            inspect(str(nofile))
        self.assertFalse(nofile.exists())
        with self.assertRaises(ValueError):
            inspect("relative.sqlite3")
        alias = pathlib.Path(self.tmp.name) / "linked.sqlite3"
        alias.symlink_to(self.path)
        with self.assertRaises(ValueError):
            inspect(str(alias))
        with self.assertRaises(ValueError):
            inspect(str(self.path.with_suffix(".db")))

    def test_corrupted_journal_fails_closed_without_mutating_db(self):
        self.writable.append(event("wait", 1, "WAIT"))
        self.writable.db.execute("DROP TRIGGER no_journal_update")
        self.writable.db.execute("UPDATE journal SET kind='PAPER_CLOSED'")
        with self.assertRaises(ValueError):
            inspect(str(self.path))
        self.assertEqual(self.writable.db.execute(
            "SELECT COUNT(*) FROM journal").fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
