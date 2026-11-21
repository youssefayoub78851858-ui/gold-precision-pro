"""Tests only synthetic, local SQLite evidence; NO market or execution."""
import copy
import datetime as dt
import json
import pathlib
import sqlite3
import tempfile
import unittest

from offline_paper_outcome_journal import OfflineJournal, ORIGIN

BASE = dt.datetime(2026, 11, 18, tzinfo=dt.timezone.utc)


def stamp(minutes):
    return (BASE + dt.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def event(name, minute, kind, trade=None):
    out = dict(eventId=name, observedUTC=stamp(minute), kind=kind,
               dataOrigin=ORIGIN, simulationOnly=True)
    if trade is not None:
        out["trade"] = trade
    return out


def close(index, gross):
    # Completed M15 01:00/02:00, H1 at 01:00/02:00,
    # H4 at 00:00. Closed and observed before each decision.
    i = index * 60
    return dict(
        id="sim_" + str(index), side="BUY" if index % 2 else "SELL",
        decisionUTC=stamp(i),
        entryUTC=stamp(i + 1),
        exitUTC=stamp(i + 30),
        firstObservedClosedUTC=stamp(i + 31),
        signalClosedUTC=stamp(i),
        signalFirstObservedUTC=stamp(i),
        contextClosedUTC=dict(H1=stamp(i), H4=stamp(0)),
        contextFirstObservedUTC=dict(H1=stamp(i), H4=stamp(0)),
        grossPnLUsd=gross, spreadUsd=0.4,
        slippageUsd=0.1, commissionUsd=0.1, initialRiskUsd=2,
        grossPnLConvention="MID_MARK_BEFORE_SPREAD_SLIPPAGE_COMMISSION",
        initialRiskConvention="STOP_LOSS_PLUS_TOTAL_MODELED_COSTS_USD"
    )


class OfflinePaperJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = pathlib.Path(self.tmp.name) / "synthetic-paper.sqlite3"
        self.j = OfflineJournal(self.file)

    def tearDown(self):
        self.j.close()

    def assert_wait(self, x):
        self.assertEqual(x["signal"], "WAIT")
        self.assertIs(x["executable"], False)
        for field in ("independentHoldoutValidated", "realMarketDataConnected",
                      "licensedDataOrBrokerFillsVerified", "paperOrderExecutionEnabled",
                      "liveOrderExecutionEnabled"):
            self.assertIs(x[field], False)
        for field in ("providerRequestsMade", "brokerOrdersSent", "paperOrdersSent"):
            self.assertEqual(x[field], 0)
        text = json.dumps(x)
        for token in ("entryPrice", "apiKey", "PRIVATE_TOKEN", '"side"'):
            self.assertNotIn(token, text)

    def test_no_licence_no_data_starts_empty_with_wait(self):
        info = self.j.summary()
        self.assert_wait(info)
        self.assertEqual(info["rows"], 0)
        self.assertEqual(info["closedPaperTrades"], 0)
        self.assertIsNone(info["modeledNetUsd"])
        self.assertIsNone(info["doubleCostStressNetUsd"])
        self.assertEqual(info["outcomeAuditStatus"], "NO_CLOSED_PAPER_TRADES")
        self.assertEqual(info["lastDigest"], "0" * 64)
        self.assertEqual(self.j.append(event("wait1", 1, "WAIT")),
                         dict(duplicate=False, recorded=True))
        self.j.append(event("lost1", 2, "SOURCE_BLOCKED"))
        state = self.j.summary()
        self.assert_wait(state)
        self.assertEqual((state["rows"], state["waitEvents"],
                          state["blockedSourceEvents"]), (2, 1, 1))
        self.j.close()
        self.j = OfflineJournal(self.file)
        self.assertEqual(self.j.summary(), state)
        self.assertEqual(self.j.append(event("wait1", 1, "WAIT")),
                         dict(duplicate=True, recorded=False))
        self.assertEqual(self.j.summary(), state)
        with self.assertRaises(ValueError):
            OfflineJournal(self.file, freeze_utc=stamp(1))

    def test_two_closes_costs_double_stress_and_durable_restart(self):
        self.j.append(event("wait", 1, "WAIT"))
        self.j.append(event("one", 92, "PAPER_CLOSED", close(1, 2)))
        self.j.append(event("two", 152, "PAPER_CLOSED", close(2, -3)))
        summary = self.j.summary()
        self.assert_wait(summary)
        self.assertEqual(summary["closedPaperTrades"], 2)
        self.assertEqual(summary["outcomeAuditStatus"],
                         "UNATTESTED_PAPER_ARITHMETIC_ONLY")
        self.assertAlmostEqual(summary["modeledNetUsd"], -2.2)
        self.assertAlmostEqual(summary["doubleCostStressNetUsd"], -3.4)
        self.assertEqual(summary["rows"], 3)
        self.assertEqual(self.j.append(event("one", 92, "PAPER_CLOSED", close(1, 2))),
                         dict(duplicate=True, recorded=False))
        self.j.close()
        self.j = OfflineJournal(self.file)
        self.assertEqual(self.j.summary(), summary)
        self.assertEqual(self.j.db.execute(
            "PRAGMA integrity_check").fetchone()[0], "ok")

    def test_bad_outcomes_conflicts_and_raw_prices_rollback(self):
        self.j.append(event("wait", 1, "WAIT"))
        before = self.j.summary()
        invalid = [
            event("beforeclose", 62, "PAPER_CLOSED", close(1, 2)),
            event("negcost", 92, "PAPER_CLOSED",
                  {**close(1, 2), "spreadUsd": -0.4}),
            event("lookahead", 92, "PAPER_CLOSED",
                  {**close(1, 2), "signalClosedUTC": stamp(75)}),
            event("wrongbasis", 92, "PAPER_CLOSED",
                  {**close(1, 2), "grossPnLConvention": "BROKER_BID_ASK"}),
            event("rawprice", 92, "PAPER_CLOSED",
                  {**close(1, 2), "entryPrice": 4000}),
            {**event("fakevendor", 92, "WAIT"), "dataOrigin": "LIVE_VERIFIED"},
            {**event("fakeauth", 92, "WAIT"), "sourceRightsVerified": True},
            {**event("fakesignal", 92, "WAIT"), "signal": "BUY"},
            event("whilerisk", 92, "WAIT", close(1, 2)),
            event("early", 0, "WAIT"),
        ]
        for bad in invalid:
            with self.subTest(event=bad["eventId"]), self.assertRaises(ValueError):
                self.j.append(bad)
            self.assertEqual(self.j.summary(), before)
        self.j.append(event("one", 92, "PAPER_CLOSED", close(1, 2)))
        state = self.j.summary()
        with self.assertRaises(ValueError):
            self.j.append(event("one", 93, "WAIT"))
        with self.assertRaises(ValueError):
            self.j.append(event("outoforder", 60, "WAIT"))
        self.assertEqual(self.j.summary(), state)

    def test_append_only_and_chain_tamper_detection(self):
        self.j.append(event("wait", 1, "WAIT"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.j.db.execute("UPDATE journal SET kind='PAPER_CLOSED'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.j.db.execute("DELETE FROM journal")
        with self.assertRaises(sqlite3.IntegrityError):
            self.j.db.execute("UPDATE settings SET freeze_utc=?", (stamp(2),))
        self.j.db.execute("DROP TRIGGER prevent_journal_update")
        self.j.db.execute("UPDATE journal SET kind='PAPER_CLOSED'")
        with self.assertRaises(ValueError):
            self.j.verify()
        with self.assertRaises(ValueError):
            self.j.append(event("two", 2, "WAIT"))


if __name__ == "__main__":
    unittest.main()
