"""External-watchdog decision policy tests; injected timestamps only."""
import datetime as dt
import unittest

from research_watchdog import assess_watchdog


NOW = dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.timezone.utc)


class ResearchWatchdogTests(unittest.TestCase):
    def assess(self, **overrides):
        values = {"process_alive": True, "paper_only": True,
                  "heartbeat_utc": "2026-11-11T11:59:30Z", "now": NOW}
        values.update(overrides)
        return assess_watchdog(**values)

    def test_fresh_paper_heartbeat_is_healthy_but_never_executable(self):
        result = self.assess()
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(result["action"], "NONE")
        self.assertEqual(result["signal"], "WAIT")
        self.assertFalse(result["executable"])

    def test_service_outage_heartbeat_loss_and_recovery_are_classified(self):
        cases = [
            ({"process_alive": False}, "PROCESS_NOT_ALIVE"),
            ({"heartbeat_utc": None}, "HEARTBEAT_MISSING"),
            ({"heartbeat_utc": "2026-11-11T11:57:59Z"}, "HEARTBEAT_STALE"),
            ({"heartbeat_utc": "2026-11-11T12:00:01Z"}, "HEARTBEAT_FROM_FUTURE"),
            ({"paper_only": False}, "PAPER_ONLY_GUARD_MISSING"),
        ]
        for change, reason in cases:
            with self.subTest(reason=reason):
                result = self.assess(**change)
                self.assertEqual(result["status"], "UNHEALTHY")
                self.assertEqual(result["action"], "RESTART_REQUIRED")
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["signal"], "WAIT")
                self.assertFalse(result["executable"])
        recovered = self.assess(heartbeat_utc="2026-11-11T11:59:59Z")
        self.assertEqual(recovered["status"], "HEALTHY")

    def test_retry_is_bounded_and_does_not_launch_a_process(self):
        result = self.assess(process_alive=False, failure_count=99, retry_max_seconds=40)
        self.assertEqual(result["retryDelaySeconds"], 40)
        self.assertNotIn("process", result)
        self.assertNotIn("pid", result)

    def test_invalid_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(stale_after_seconds=0)
        with self.assertRaises(ValueError):
            self.assess(failure_count=-1)


if __name__ == "__main__":
    unittest.main()
