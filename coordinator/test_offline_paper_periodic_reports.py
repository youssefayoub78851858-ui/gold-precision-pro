"""Regression tests for read-only synthetic results, not live trading accuracy."""
from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import tempfile
import unittest

from offline_paper_outcome_journal import OfflineJournal
from offline_paper_periodic_reports import make_report
from test_offline_paper_outcome_journal import event, close, stamp


def closed_at(index, gross):
    trade = copy.deepcopy(close(index, gross))
    # Existing simple fixture assumes H4 closed at midnight; after 04:00
    # roll to the most recently closed 4h period, observed before decision.
    most_recent_h4 = (index // 4) * 240
    trade["contextClosedUTC"]["H4"] = stamp(most_recent_h4)
    trade["contextFirstObservedUTC"]["H4"] = stamp(most_recent_h4)
    return event("simclose_" + str(index), index * 60 + 32,
                 "PAPER_CLOSED", trade)


class SyntheticPeriodicReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "local_test.sqlite3"
        self.db = OfflineJournal(self.path)

    def tearDown(self):
        self.db.close()

    def safe(self, data):
        self.assertEqual(data["mode"], "GOLD_OFFLINE_SYNTHETIC_PAPER_REPORTS_V1")
        self.assertEqual(data["status"], "OFFLINE_SYNTHETIC_DESCRIPTIVE_ONLY")
        self.assertEqual(data["signal"], "WAIT")
        self.assertIs(data["executable"], False)
        for field in (
            "unverifiedNextM15ForecastAccuracy",
            "firstHundredClosedTradeCheckpoint",
        ):
            if data["cumulative"]["closedTrades"] < 100:
                self.assertIsNone(data[field])
        for field in (
            "realMarketDataConnected", "brokerTransactionCostsVerified",
            "independentHoldoutValidated", "statisticallyValidated",
            "paperOrderExecutionEnabled", "liveOrderExecutionEnabled",
        ):
            self.assertIs(data[field], False, field)
        for field in ("providerRequestsMade", "brokerOrdersSent",
                      "paperOrdersSent"):
            self.assertEqual(data[field], 0)
        serialized = json.dumps(data)
        for prohibited in ('"side"', '"entryUTC"', '"grossPnLUsd"',
                           "apiKey", "entryPrice", "MONITOR_READONLY_TOKEN"):
            self.assertNotIn(prohibited, serialized)

    def test_empty_wait_gap_and_restart_stay_unproven(self):
        empty = make_report(self.db)
        self.safe(empty)
        self.assertIsNone(empty["cumulative"]["winRate"])
        self.assertEqual(empty["journalRows"], 0)
        self.assertEqual(empty["dailyUTC"], [])
        self.assertEqual(empty["weeklyUTC"], [])
        self.assertEqual(empty["completedFiveTradeBatches"], [])
        self.db.append(event("wait", 1, "WAIT"))
        self.db.append(event("disconnected", 2, "SOURCE_BLOCKED"))
        state = make_report(self.db)
        self.safe(state)
        self.assertEqual(state["cumulative"]["closedTrades"], 0)
        self.assertEqual(state["dailyUTC"][0]["waitEvents"], 1)
        self.assertEqual(state["weeklyUTC"][0]["blockedSourceEvents"], 1)
        self.assertEqual(state["partialFiveTradeBatchCount"], 0)
        self.db.close()
        self.db = OfflineJournal(self.path)
        self.assertEqual(make_report(self.db), state)
        self.db.append(event("wait", 1, "WAIT"))  # Idempotent replay
        self.assertEqual(make_report(self.db), state)

    def test_five_batch_seven_closes_and_next_week(self):
        self.db.append(event("wait", 1, "WAIT"))
        self.db.append(event("outage", 2, "SOURCE_BLOCKED"))
        for i in range(1, 7):
            self.db.append(closed_at(i, 2 if i % 2 else -3))
        self.db.append(closed_at(170, -3))  # UTC Monday of following week
        report = make_report(self.db)
        self.safe(report)
        self.assertEqual(report["journalRows"], 9)
        self.assertEqual(report["cumulative"]["closedTrades"], 7)
        self.assertAlmostEqual(report["cumulative"]["netModeledUsd"], -10.2)
        self.assertAlmostEqual(report["cumulative"]["netDoubleCostStressUsd"], -14.4)
        self.assertEqual(report["partialFiveTradeBatchCount"], 2)
        self.assertEqual(len(report["completedFiveTradeBatches"]), 1)
        first = report["completedFiveTradeBatches"][0]
        self.assertEqual(first["closedTradeRange"], [1, 5])
        self.assertEqual(first["closedTrades"], 5)
        self.assertEqual(first["independentlyValidated"], False)
        self.assertEqual(len(report["weeklyUTC"]), 2)
        self.assertEqual(report["weeklyUTC"][0]["closedTrades"], 6)
        self.assertEqual(report["weeklyUTC"][1]["closedTrades"], 1)
        self.assertEqual(report["weeklyUTC"][0]["waitEvents"], 1)
        self.assertEqual(report["weeklyUTC"][0]["blockedSourceEvents"], 1)
        self.assertEqual(sum(x["closedTrades"] for x in report["dailyUTC"]), 7)
        self.db.close()
        self.db = OfflineJournal(self.path)
        self.assertEqual(make_report(self.db), report)

    def test_hundred_closed_trade_checkpoint_never_accuracy_claim(self):
        # 100 fabricated outcomes are not 100 timestamped forecasts, and
        # none has an independently verified fill or BID/ASK history.
        for i in range(1, 101):
            self.db.append(closed_at(i, 2 if i % 2 else -3))
        result = make_report(self.db)
        self.safe(result)
        self.assertEqual(result["cumulative"]["closedTrades"], 100)
        self.assertEqual(result["partialFiveTradeBatchCount"], 0)
        self.assertEqual(len(result["completedFiveTradeBatches"]), 20)
        self.assertEqual(result["firstHundredClosedTradeCheckpoint"]["closedTrades"], 100)
        self.assertIs(result["firstHundredClosedTradeCheckpoint"]["independentlyValidated"], False)
        self.assertIsNone(result["unverifiedNextM15ForecastAccuracy"])
        self.assertIs(result["statisticallyValidated"], False)
        self.assertEqual(
            result["firstHundredClosedTradeCheckpoint"]["netModeledUsd"],
            result["cumulative"]["netModeledUsd"],
        )

    def test_corrupted_journal_cannot_publish_a_report(self):
        self.db.append(event("one", 1, "WAIT"))
        self.db.db.execute("DROP TRIGGER no_journal_update")
        self.db.db.execute("UPDATE journal SET kind='PAPER_CLOSED'")
        with self.assertRaises(ValueError):
            make_report(self.db)


if __name__ == "__main__":
    unittest.main()
