"""Pre-license operational drill: actual intake -> V3/r2 -> isolated SQLite paper.

No provider transport, keys, market prices, cloud storage, orders, or automatic
activation. All candles are generated test fixtures, and every public decision
remains WAIT. This tests controlled recovery without pretending profitability.
"""
from __future__ import annotations

import copy
import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from test_xauusd_research_pipeline import fixture_bundle, simulate
from ultimate_paper import PaperAccount
from xauusd_feed_gate import SourcePolicy
from xauusd_research_pipeline import run_research_pipeline


class PreLicenseOperationalCommissioning(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = pathlib.Path(tmp.name) / "offline-drill.sqlite3"
        self.payload, self.context, self.now = fixture_bundle()

    def check_wait(self, report):
        self.assertEqual(report["signal"], "WAIT")
        self.assertIs(report["executable"], False)
        self.assertIs(report["researchEligible"], False)
        self.assertEqual(report["researchCandidate"], "NONE")
        self.assertEqual(report["providerRequestsMade"], 0)

    def test_default_startup_quarantines_synthetic_and_unlicensed_live(self):
        with patch("xauusd_research_pipeline.subprocess.run",
                   side_effect=AssertionError("engines must not start")):
            startup = run_research_pipeline(self.payload, self.now,
                                            SourcePolicy(), self.context)
            self.check_wait(startup)
            self.assertNotIn("paperSnapshot", startup)
            unlicensed = copy.deepcopy(self.payload)
            unlicensed["mode"] = "live"
            unlicensed["priceBasis"] = "BID"
            live = run_research_pipeline(unlicensed, self.now,
                                         SourcePolicy(), self.context)
            self.check_wait(live)
            self.assertEqual(live["engines"]["paper"], "SKIPPED")
            self.assertNotIn("paperSnapshot", live)
        self.assertFalse(self.db_path.exists())

    def test_simulation_reboot_kill_and_source_gap_never_create_orders(self):
        approved_for_test = simulate(self.payload, self.context, self.now)
        self.check_wait(approved_for_test)
        self.assertIs(approved_for_test["simulationOnly"], True)
        self.assertEqual(approved_for_test["engines"]["v3"], "REVIEWED")
        paper = approved_for_test["paperSnapshot"]
        self.assertEqual(paper["frames"]["M15"][-1]["dataOrigin"],
                         "SYNTHETIC_TEST_ONLY")
        last_bar = paper["frames"]["M15"][-1]
        db = PaperAccount(self.db_path)
        try:
            first = db.step(last_bar, paper)
            self.assertEqual(len(first["pending"]), 1)
            self.assertEqual(first["trades"], [])
            self.assertEqual(first["account"]["balance"], 10000)
        finally:
            db.close()

        db = PaperAccount(self.db_path)
        try:
            # A second worker replaying the same closed bar after restart must
            # not place a duplicate paper entry or persist a duplicate signal.
            self.assertEqual(db.step(last_bar, paper), {"duplicate": True})
            before = db.summary()
            broken = {**last_bar, "high": last_bar["low"] - 1}
            with self.assertRaises(ValueError):
                db.step(broken, paper)
            self.assertEqual(db.summary(), before)

            # A disconnected source triggers the OFFLINE kill switch. This
            # cancels any pending synthetic entry before the next closed bar.
            db.kill()
            self.assertEqual(db.summary()["pending"], [])
        finally:
            db.close()

        db = PaperAccount(self.db_path)
        try:
            next_open = self.now.isoformat().replace("+00:00", "Z")
            result = db.step({"datetime": next_open, "open": 104,
                              "high": 105, "low": 103, "close": 104,
                              "dataOrigin": "SYNTHETIC_TEST_ONLY"})
            self.assertEqual(result["position"], [])
            self.assertEqual(result["pending"], [])
            self.assertEqual(result["trades"], [])
            self.assertEqual(result["account"]["balance"], 10000)
            self.assertEqual(result["account"]["killed"], 1)
            self.assertEqual(db.step({"datetime": next_open, "open": 104,
                "high": 105, "low": 103, "close": 104,
                "dataOrigin": "SYNTHETIC_TEST_ONLY"}), {"duplicate": True})
            self.assertEqual(db.db.execute(
                "SELECT COUNT(*) FROM events WHERE kind='PAPER_ENTRY'"
            ).fetchone()[0], 0)

            # A later fresh bar and a forged optimistic BUY research
            # candidate still MUST NOT reset the persisted kill switch.
            # Only an explicitly separate manual action may do so.
            later_time = (self.now + dt.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
            later_closed = (self.now + dt.timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
            candidate = {"signal": "WAIT", "executable": False,
                         "researchCandidate": "BUY", "risk": {"ok": True},
                         "tradePlan": {"stop": 95, "target": 110}}
            restored = db.step(
                {"datetime": later_time, "open": 104, "high": 105,
                 "low": 103, "close": 104, "dataOrigin": "SYNTHETIC_TEST_ONLY"},
                {"asOfUTC": later_closed},
                evaluator=lambda _: candidate)
            self.assertEqual(restored["account"]["killed"], 1)
            self.assertEqual(restored["position"], [])
            self.assertEqual(restored["pending"], [])
            self.assertEqual(restored["trades"], [])
            self.assertEqual(db.db.execute(
                "SELECT COUNT(*) FROM events WHERE kind='PAPER_ENTRY'"
            ).fetchone()[0], 0)
        finally:
            db.close()

    def test_feed_gap_never_enters_v3_or_paper_ledger(self):
        bad = copy.deepcopy(self.payload)
        bad["frames"]["15min"]["candles"].pop(4)
        result = simulate(bad, self.context, self.now)
        self.check_wait(result)
        self.assertEqual(result["engines"]["v3"], "SKIPPED")
        self.assertEqual(result["engines"]["paper"], "SKIPPED")
        self.assertNotIn("paperSnapshot", result)
        self.assertFalse(self.db_path.exists())


if __name__ == "__main__":
    unittest.main()
