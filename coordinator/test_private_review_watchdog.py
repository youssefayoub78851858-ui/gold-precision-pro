"""Offline periodic review audit; no network, orders, or shared production state."""
import datetime as dt
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from private_review_watchdog import (
    audit_once, disabled_state, read_audit_state, run_until_stopped,
    FOLDER, ALERT_DB, NOTICE_DB
)
from test_eodhd_research_bridge import NOW


class ReviewWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_disabled_or_missing_never_creates_db(self):
        x = read_audit_state(self.root, NOW, enabled=False)
        self.assertEqual(x, disabled_state())
        x = read_audit_state(self.root, NOW, enabled=True)
        self.assertEqual(x["status"], "AUDIT_NOT_STARTED")
        self.assertEqual(list(self.root.rglob("*.sqlite3")), [])

    def test_outage_is_recorded_once_and_survives_restart(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = audit_once(self.root, NOW)
            again = audit_once(self.root, NOW + dt.timedelta(seconds=10))
        self.assertEqual(first["status"], "AUDIT_OK")
        self.assertEqual(first["signal"], "WAIT")
        self.assertIs(first["executable"], False)
        self.assertFalse(first["paperRunning"])
        self.assertEqual(first["externalNotificationsSent"], 0)
        self.assertIn("INTAKE_BLOCKED", first["alertCodes"])
        self.assertEqual(first["lastNotificationCode"], "WAIT_EODHD_INTAKE")
        self.assertEqual(again["status"], "AUDIT_OK")
        self.assertEqual(len(list((self.root / FOLDER).glob("*.sqlite3"))), 2)
        with sqlite3.connect(self.root / FOLDER / ALERT_DB) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM research_alert_events").fetchone()[0], 1)
        with sqlite3.connect(self.root / FOLDER / NOTICE_DB) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM research_notification_events").fetchone()[0], 1)
        after = read_audit_state(self.root, NOW + dt.timedelta(seconds=10), enabled=True)
        self.assertEqual(after["lastObservedUTC"], again["lastObservedUTC"])
        self.assertEqual(after["ageSeconds"], 0)

    def test_stale_and_invalid_private_storage(self):
        audit_once(self.root, NOW)
        stale = read_audit_state(self.root, NOW + dt.timedelta(seconds=125), enabled=True)
        self.assertEqual(stale["status"], "AUDIT_STALE")
        self.assertEqual(stale["signal"], "WAIT")
        folder = self.root / FOLDER
        (folder / ALERT_DB).unlink()
        (folder / ALERT_DB).symlink_to(self.root / "elsewhere")
        bad = read_audit_state(self.root, NOW, enabled=True)
        self.assertEqual(bad["status"], "AUDIT_UNAVAILABLE")
        self.assertFalse(bad["executable"])

    def test_blocking_attacker_snapshot_never_executes_paper(self):
        path = self.root / "eodhd-private-review.json"
        path.write_text('{"signal":"BUY","executable":true,"apiKey":"PRIVATE-KEY"}')
        path.chmod(0o600)
        stamp=NOW.timestamp()-1
        os.utime(path, (stamp, stamp))
        x = audit_once(self.root, NOW)
        text = str(x)
        self.assertIn("AUDIT_OK", text)
        self.assertNotIn("PRIVATE-KEY", text)
        self.assertNotIn("'BUY'", text)
        self.assertIs(x["executable"], False)
        self.assertFalse(x["paperRunning"])

    def test_offline_loop_is_stoppable_and_debounced(self):
        stop = threading.Event()
        polls = []
        def once(directory, now=None):
            polls.append(now)
            if len(polls) == 2: stop.set()
            return {"signal": "WAIT"}
        def wait(seconds):
            self.assertEqual(seconds, 60)
            return False
        stop.wait = wait
        with patch("private_review_watchdog.audit_once", side_effect=once):
            run_until_stopped(self.root, stop, clock=lambda: NOW)
        self.assertEqual(len(polls), 2)

    def test_reject_symlink_audit_directory(self):
        (self.root / FOLDER).symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            audit_once(self.root, NOW)


if __name__ == "__main__":
    unittest.main()
