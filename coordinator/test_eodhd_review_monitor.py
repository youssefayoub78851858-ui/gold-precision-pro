"""EODHD private-review monitor: offline outage, restart and security tests."""
import copy
import datetime as dt
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from eodhd_review_monitor import observe_once, poll_private_review
from test_eodhd_research_bridge import NOW, sample

class PrivateReviewMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.path = self.root / "eodhd-private-review.json"
        self.alert_db = self.root / "alerts.sqlite3"
        self.notification_db = self.root / "notices.sqlite3"

    def write(self, snapshot=None, file_age=1):
        value = sample(16) if snapshot is None else snapshot
        self.path.write_text(json.dumps(value))
        self.path.chmod(0o600)
        stamp = NOW.timestamp() - file_age
        os.utime(self.path, (stamp, stamp))

    def assert_safe(self, x):
        s = json.dumps(x, sort_keys=True)
        self.assertIn('"signal": "WAIT"', s)
        self.assertNotIn('"signal": "BUY"', s)
        self.assertNotIn('"signal": "SELL"', s)
        self.assertNotIn('"executable": true', s)
        self.assertNotIn('"researchEligible": true', s)
        self.assertNotIn('"bid":', s)
        self.assertNotIn('"ask":', s)
        self.assertNotIn('"latestQuote"', s)
        self.assertNotIn('"paperSnapshot"', s)
        self.assertNotIn("3900.", s)
        self.assertEqual(x["result"]["sourceRequestsMade"], 0)
        self.assertEqual(x["result"]["engineStatus"], "NOT_INVOKED")
        self.assertFalse(x["result"]["paperRunning"])

    def test_missing_and_no_repeat_after_restart(self):
        a = observe_once(self.root, self.alert_db, self.notification_db, NOW)
        self.assert_safe(a)
        self.assertEqual(a["result"]["dataStatus"], "NOT_CONNECTED")
        self.assertEqual(len(a["alerts"]["events"]), 1)
        self.assertEqual(a["alerts"]["events"][0]["transition"], "RAISED")
        self.assertEqual(a["notifications"]["current"]["signal"], "WAIT")
        b = observe_once(self.root, self.alert_db, self.notification_db,
                         NOW + dt.timedelta(seconds=1))
        self.assertEqual(b["alerts"]["events"], [])
        self.assertEqual(b["notifications"]["events"], [])
        self.assert_safe(b)

    def test_fresh_snapshot_blocked_from_engines_but_recorded_as_pending(self):
        self.write()
        with patch("eodhd_research_bridge.run_research_pipeline",
                   side_effect=AssertionError("no engine until separately approved")):
            x = observe_once(self.root, self.alert_db, self.notification_db, NOW)
        self.assert_safe(x)
        self.assertEqual(x["result"]["dataStatus"], "WAIT_REVIEW_OBSERVATION_ONLY")
        self.assertIn("SOURCE_RIGHTS_OR_PROVIDER_APPROVAL_MISSING",
                      x["result"]["intake"]["blockingReasons"])
        self.assertIn("INDEPENDENT_SESSION_HISTORY_OR_CLOCK_EVIDENCE_MISSING",
                      x["result"]["intake"]["blockingReasons"])
        self.assertEqual(x["notifications"]["current"]["kind"], "DATA_ALERT")
        self.assertEqual(x["notifications"]["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
        self.assertEqual(x["alerts"]["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")

    def test_stale_snapshot_blocks_and_records_recovery_transitions(self):
        self.write(file_age=100)
        old = observe_once(self.root, self.alert_db, self.notification_db, NOW)
        self.assert_safe(old)
        self.assertEqual(old["result"]["dataStatus"], "WAIT_STALE")
        self.write()
        updated = observe_once(self.root, self.alert_db, self.notification_db, NOW)
        self.assert_safe(updated)
        self.assertTrue(any(x["transition"] == "RECOVERED" for x in updated["alerts"]["events"]))
        self.assertTrue(any(x["transition"] == "RAISED" for x in updated["alerts"]["events"]))

    def test_corruption_permissions_symlink_and_tampered_bidask_fail_closed(self):
        self.write()
        self.path.chmod(0o644)
        self.assertEqual(poll_private_review(self.root, NOW)["dataStatus"], "BLOCKED")
        self.path.unlink()
        self.path.symlink_to(self.root / "elsewhere")
        self.assertEqual(poll_private_review(self.root, NOW)["dataStatus"], "BLOCKED")
        self.path.unlink()
        broken = sample(16)
        broken["bidFrames"]["M15"][-1]["high"] += 100000
        self.write(broken)
        x = poll_private_review(self.root, NOW)
        self.assertIn("BID_ASK_CROSSED", x["intake"]["blockingReasons"])
        self.assertEqual(x["dataStatus"], "BLOCKED")
        self.assertEqual(x["signal"], "WAIT")
        self.assertFalse(x["executable"])
        self.path.write_text("{invalid")
        self.path.chmod(0o600)
        os.utime(self.path, (NOW.timestamp()-1, NOW.timestamp()-1))
        self.assertEqual(poll_private_review(self.root, NOW)["dataStatus"], "BLOCKED")

    def test_snapshot_changed_between_safe_checks_cannot_count_as_recovered(self):
        self.write()
        with patch("eodhd_review_monitor._read_private_snapshot",
                   side_effect=OSError("file replaced during read")):
            blocked = poll_private_review(self.root, NOW)
        self.assert_safe(blocked)
        self.assertEqual(blocked["dataStatus"], "BLOCKED")
        self.assertIn("EODHD_PRIVATE_SNAPSHOT_READ_REJECTED",
                      blocked["intake"]["blockingReasons"])

    def test_unsafe_source_claims_do_not_propagate(self):
        snap = sample()
        snap["signal"] = "BUY"
        snap["executable"] = True
        snap["researchEligible"] = True
        self.write(snap)
        x = observe_once(self.root, self.alert_db, self.notification_db, NOW)
        self.assert_safe(x)
        self.assertEqual(x["result"]["dataStatus"], "BLOCKED")

    def test_unauthenticated_status_file_never_triggers_network(self):
        self.write()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            with patch("eodhd_review_monitor.review_eodhd_snapshot",
                       wraps=__import__("eodhd_review_monitor").review_eodhd_snapshot) as called:
                r = poll_private_review(self.root, NOW)
            self.assertEqual(called.call_count, 1)
        self.assertFalse(r["researchEligible"])
        self.assertEqual(r["sourceDataMode"], "eodhd_private_unverified")

if __name__ == "__main__":
    unittest.main()
