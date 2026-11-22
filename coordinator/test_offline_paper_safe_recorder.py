"""Synthetic-only event-driven recorder tests. No Render or broker writes."""
import copy
import pathlib
import tempfile
import unittest

from offline_paper_outcome_journal import OfflineJournal, ORIGIN
from offline_paper_safe_recorder import record, gate_ok, MODE
from test_offline_paper_outcome_journal import event, close, stamp


def gate():
    return {
        "mode": "GOLD_PAPER_STARTUP_RECOVERY_GATE_V1",
        "status": "STARTUP_LOCAL_CHECKPOINT_READ_ONLY_VERIFIED",
        "checkpointSafe": True,
        "paperResultsDisplayAllowed": True,
        "backupOffsiteVerified": False,
        "independentHoldoutValidated": False,
        "marketDataConnected": False,
        "paperOrdersAllowed": False,
        "liveOrdersAllowed": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "signal": "WAIT",
        "executable": False,
    }


def packet(name, minute, state="OBSERVED_CLOSED", trade=None):
    obj = {
        "observationId": name,
        "observedUTC": stamp(minute),
        "sourceState": state,
        "signal": "WAIT",
        "executable": False,
        "dataOrigin": ORIGIN,
        "simulationOnly": True,
    }
    if trade is not None:
        obj["trade"] = trade
    return obj


class SafeSyntheticAutoRecorder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = pathlib.Path(self.temp.name) / "synthetic.sqlite3"
        self.j = OfflineJournal(self.file)

    def tearDown(self):
        self.j.close()

    def check_wait(self, result):
        self.assertEqual(result["mode"], MODE)
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        for k in ("realMarketDataConnected", "independentHoldoutValidated",
                  "paperOrdersAllowed", "liveOrdersAllowed"):
            self.assertIs(result[k], False)
        for k in ("providerRequestsMade", "brokerOrdersSent", "paperOrdersSent"):
            self.assertEqual(result[k], 0)

    def test_no_disk_checkpoint_or_real_feed_can_start_recorder(self):
        original = self.j.summary()
        for false_gate in (
            None, {}, {"mode": "INVALID"}, {**gate(), "signal": "BUY"},
            {**gate(), "backupOffsiteVerified": True},
            {**gate(), "checkpointSafe": False},
            {**gate(), "paperResultsDisplayAllowed": False},
            {**gate(), "marketDataConnected": True},
            {**gate(), "liveOrdersAllowed": True},
        ):
            self.assertFalse(gate_ok(false_gate))
            with self.assertRaises(ValueError):
                record(self.j, false_gate, packet("blocked", 1))
            self.assertEqual(self.j.summary(), original)
        for altered in (
            {**packet("not-synthetic", 1), "dataOrigin": "LIVE_MARKET"},
            {**packet("invalid", 1), "simulationOnly": False},
            {**packet("signal", 1), "signal": "BUY"},
            {**packet("executable", 1), "executable": True},
            {**packet("extra", 1), "brokerToken": "never_read"},
            packet("needs-trade", 1, "PAPER_CLOSE"),
            packet("invalid-trade", 1, "SOURCE_DOWN", close(1, 2)),
            {**packet("invalid-time", 1), "observedUTC": "2026-11-18T01:00:00+00:00"},
        ):
            with self.assertRaises((ValueError, TypeError)):
                record(self.j, gate(), altered)
            self.assertEqual(self.j.summary(), original)

    def test_outage_gap_and_two_good_observations_allow_only_synthetic_close(self):
        for n, minute in (("first", 1), ("second", 2)):
            result = record(self.j, gate(), packet(n, minute))
            self.check_wait(result)
            self.assertEqual(result["eventKind"], "WAIT")
            self.assertTrue(result["recorded"])
        # A candidate result after a missing hour is quarantined, not
        # treated as a profitable trade.
        out_of_window = packet("gapclose", 92, "PAPER_CLOSE", close(1, 2))
        gap = record(self.j, gate(), out_of_window)
        self.check_wait(gap)
        self.assertEqual(gap["eventKind"], "SOURCE_BLOCKED")
        self.assertEqual(self.j.summary()["closedPaperTrades"], 0)
        self.assertEqual(self.j.summary()["blockedSourceEvents"], 1)
        self.assertEqual(record(self.j, gate(), out_of_window)["status"],
                         "DUPLICATE_SKIPPED")
        # One new healthy observation cannot unlock paper closes.
        record(self.j, gate(), packet("reconnect1", 93))
        candidate = packet("too_soon", 94, "PAPER_CLOSE", close(1, 2))
        result = record(self.j, gate(), candidate)
        self.assertEqual(result["eventKind"], "SOURCE_BLOCKED")
        # After this new block, TWO separate healthy observations are needed.
        record(self.j, gate(), packet("recover1", 95))
        record(self.j, gate(), packet("recover2", 96))
        accepted = record(self.j, gate(), packet("approved", 97,
                                                "PAPER_CLOSE", close(1, 2)))
        self.check_wait(accepted)
        self.assertEqual(accepted["eventKind"], "PAPER_CLOSED")
        summary = self.j.summary()
        self.assertEqual(summary["closedPaperTrades"], 1)
        self.assertAlmostEqual(summary["modeledNetUsd"], 1.4)
        self.assertEqual(summary["brokerOrdersSent"], 0)
        self.assertFalse(summary["realMarketDataConnected"])
        self.assertEqual(summary["blockedSourceEvents"], 2)
        # A second close without two new observations is quarantined.
        different_trade = copy.deepcopy(close(1, 2))
        different_trade["id"] = "second_sim"
        after = record(self.j, gate(), packet("soon_again", 98,
                                              "PAPER_CLOSE", different_trade))
        self.assertEqual(after["eventKind"], "SOURCE_BLOCKED")
        self.assertEqual(self.j.summary()["closedPaperTrades"], 1)

    def test_same_packet_replayed_after_restart_is_exactly_once(self):
        one = packet("tick", 1)
        initial = record(self.j, gate(), one)
        self.assertEqual(initial["status"], "OFFLINE_EVENT_RECORDED")
        self.assertEqual(initial["eventKind"], "WAIT")
        self.j.close()
        self.j = OfflineJournal(self.file)
        duplicate = record(self.j, gate(), one)
        self.check_wait(duplicate)
        self.assertEqual(duplicate["status"], "DUPLICATE_SKIPPED")
        self.assertFalse(duplicate["recorded"])
        self.assertEqual(self.j.summary()["rows"], 1)
        # Source mutating same observationId with a changed payload gets a
        # NEW digest, but same observedUTC: cannot silently overwrite history.
        tampered = {**one, "sourceState": "SOURCE_DOWN"}
        with self.assertRaises(ValueError):
            record(self.j, gate(), tampered)
        self.assertEqual(self.j.summary()["rows"], 1)

    def test_declared_outage_blocks_until_recovery_observed(self):
        record(self.j, gate(), packet("one", 89))
        record(self.j, gate(), packet("two", 90))
        outage = record(self.j, gate(), packet("offline", 91, "SOURCE_DOWN"))
        self.assertEqual(outage["eventKind"], "SOURCE_BLOCKED")
        first = record(self.j, gate(), packet("first_return", 92))
        self.assertEqual(first["eventKind"], "WAIT")
        pending = record(self.j, gate(), packet("candidate", 93,
                                               "PAPER_CLOSE", close(1, 2)))
        self.assertEqual(pending["eventKind"], "SOURCE_BLOCKED")
        self.assertEqual(self.j.summary()["closedPaperTrades"], 0)

    def test_hash_chain_violation_prevents_next_packet(self):
        record(self.j, gate(), packet("tick", 1))
        self.j.db.execute("DROP TRIGGER no_journal_update")
        self.j.db.execute("UPDATE journal SET kind='SOURCE_BLOCKED'")
        with self.assertRaises(ValueError):
            record(self.j, gate(), packet("next", 2))
        self.assertEqual(self.j.db.execute(
            "SELECT COUNT(*) FROM journal").fetchone()[0], 1)

    def test_write_lock_rechecks_new_outage_from_another_writer(self):
        record(self.j, gate(), packet("first", 89))
        record(self.j, gate(), packet("second", 90))
        # An eligible synthetic close at 93 would be recorded if the
        # observed journal still ended with those two WAIT rows.
        other = OfflineJournal(self.file)
        original_append = self.j.append
        def concurrent(proposed, prior_guard=None):
            # Race: source falls over at 92 before first connection
            # acquires BEGIN IMMEDIATE. Must not record PAPER_CLOSED.
            other.append(event("parallel_outage", 92, "SOURCE_BLOCKED"))
            return original_append(proposed, prior_guard=prior_guard)
        self.j.append = concurrent
        try:
            with self.assertRaises(ValueError):
                record(self.j, gate(), packet("close", 93,
                                              "PAPER_CLOSE", close(1, 2)))
        finally:
            self.j.append = original_append
            other.close()
        self.assertEqual(self.j.summary()["rows"], 3)
        self.assertEqual(self.j.summary()["closedPaperTrades"], 0)
        self.assertEqual(self.j.summary()["blockedSourceEvents"], 1)


if __name__ == "__main__":
    unittest.main()
