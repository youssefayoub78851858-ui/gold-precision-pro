"""Offline recovery: repeated file observations NEVER establish tradable evidence."""
import datetime as dt
import json
import os
import pathlib
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from private_feed_recovery import observe_recovery, read_recovery
from private_review_watchdog import audit_once, read_audit_state, FOLDER
from test_eodhd_research_bridge import NOW, sample


def fake(status="WAIT_REVIEW_OBSERVATION_ONLY", **override):
    return {"status": "WAIT_EODHD_INTAKE", "dataStatus": status,
            "signal": "WAIT", "executable": False, "researchEligible": False,
            "paperRunning": False, "engineStatus": "NOT_INVOKED",
            "sourceRequestsMade": 0, **override}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.db = self.root / "recovery.sqlite3"

    def safe(self, result):
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])
        self.assertFalse(result["sourceVerified"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertNotIn("bid", json.dumps(result))
        self.assertNotIn("ask", json.dumps(result))

    def test_no_file_is_read_only_not_started(self):
        r = read_recovery(self.db, NOW)
        self.assertEqual(r["state"], "RECOVERY_NOT_STARTED")
        self.safe(r)
        self.assertFalse(self.db.exists())

    def test_loss_then_three_separate_observations_then_interrupt(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            a = observe_recovery(self.db, fake("NOT_CONNECTED"), NOW)
            self.assertEqual(a["state"], "SOURCE_ABSENT")
            one = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=60))
            self.assertEqual(one["consecutiveObservations"], 1)
            repeat = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=60))
            self.assertEqual(repeat, one)
            two = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=120))
            self.assertEqual(two["consecutiveObservations"], 2)
            three = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=180))
        self.assertEqual(three["state"], "OBSERVATION_REPEATED_UNVERIFIED")
        self.assertEqual(three["consecutiveObservations"], 3)
        self.safe(three)
        self.assertEqual(read_recovery(self.db, NOW + dt.timedelta(seconds=185))["state"],
                         "OBSERVATION_REPEATED_UNVERIFIED")
        # Reuse the same persistent SQLite file after object/process restart.
        interrupted = observe_recovery(self.db, fake("WAIT_STALE"),
                                       NOW + dt.timedelta(seconds=240))
        self.assertEqual(interrupted["state"], "SOURCE_INTERRUPTED")
        self.assertEqual(interrupted["consecutiveObservations"], 0)
        self.safe(interrupted)
        resumed = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=300))
        self.assertEqual(resumed["consecutiveObservations"], 1)
        self.assertEqual(resumed["state"], "OBSERVATION_SEEN_UNVERIFIED")
        self.assertGreaterEqual(resumed["transitionCount"], 3)
        self.assertEqual(read_recovery(self.db, NOW + dt.timedelta(seconds=450))["state"],
                         "RECOVERY_STALE")

    def test_gap_clock_rollback_and_spoofed_evidence_never_unlocks(self):
        observe_recovery(self.db, fake(), NOW)
        with self.assertRaises(ValueError):
            observe_recovery(self.db, fake("NOT_CONNECTED"), NOW)
        with self.assertRaises(ValueError):
            observe_recovery(self.db, fake(), NOW - dt.timedelta(seconds=1))
        after_gap = observe_recovery(self.db, fake(), NOW + dt.timedelta(seconds=130))
        self.assertEqual(after_gap["consecutiveObservations"], 1)
        forged = observe_recovery(self.db, fake("WAIT_REVIEW_OBSERVATION_ONLY",
            signal="BUY", executable=True, paperRunning=True, secret="PRIVATE-TOKEN"),
            NOW + dt.timedelta(seconds=190))
        self.assertEqual(forged["state"], "SOURCE_REJECTED")
        self.safe(forged)
        self.assertNotIn("PRIVATE-TOKEN", json.dumps(forged))

    def test_symlink_is_refused_and_corrupt_state_fails_closed(self):
        self.db.symlink_to(self.root / "other")
        with self.assertRaises(ValueError):
            observe_recovery(self.db, fake(), NOW)
        self.assertEqual(read_recovery(self.db, NOW)["state"], "RECOVERY_UNAVAILABLE")
        self.db.unlink()
        self.db.write_text("not SQLite")
        self.db.chmod(0o600)
        self.assertEqual(read_recovery(self.db, NOW)["state"], "RECOVERY_UNAVAILABLE")

    def test_end_to_end_watchdog_missing_fresh_stale(self):
        with patch.object(socket, "socket", side_effect=AssertionError("no network")):
            a = audit_once(self.root, NOW)
            self.assertEqual(a["recovery"]["state"], "SOURCE_ABSENT")
            path = self.root / "eodhd-private-review.json"
            for index in range(1, 4):
                at = NOW + dt.timedelta(seconds=index * 60)
                snapshot = sample(16)
                snapshot["latestQuote"]["timeUTC"] = at.isoformat()
                path.write_text(json.dumps(snapshot))
                path.chmod(0o600)
                os.utime(path, (at.timestamp() - 1, at.timestamp() - 1))
                result = audit_once(self.root, at)
                self.safe(result["recovery"])
                self.assertEqual(result["recovery"]["consecutiveObservations"], index)
            self.assertEqual(result["recovery"]["state"], "OBSERVATION_REPEATED_UNVERIFIED")
            stopped = audit_once(self.root, NOW + dt.timedelta(seconds=260))
            self.assertEqual(stopped["recovery"]["state"], "SOURCE_INTERRUPTED")
            self.assertFalse(stopped["recovery"]["paperOrdersAllowed"])
            self.assertEqual(stopped["signal"], "WAIT")
            self.assertEqual(read_audit_state(self.root, NOW + dt.timedelta(seconds=261),
                                              enabled=True)["recovery"]["state"],
                             "SOURCE_INTERRUPTED")


if __name__ == "__main__":
    unittest.main()
