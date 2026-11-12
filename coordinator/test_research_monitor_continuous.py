"""Continuous scheduler uses injected time and exits cleanly in DRY_RUN."""
import datetime as dt
import pathlib
import tempfile
import unittest

from research_monitor import ResearchAlertMonitor
from research_monitor_runner import ResearchMonitorRunner
from research_notification import ResearchNotificationJournal


class SimulatedClock:
    def __init__(self):
        self.now = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += dt.timedelta(seconds=seconds)


class ResearchMonitorContinuousTests(unittest.TestCase):
    def test_continuous_loop_yields_without_accumulating_and_stops_on_request(self):
        clock = SimulatedClock()
        healthy = {"status": "SYNTHETIC_TEST_ONLY", "sourceDataMode": "synthetic",
                   "simulationOnly": True, "researchEligible": False,
                   "signal": "WAIT", "executable": False}
        poll_count = 0

        def poll():
            nonlocal poll_count
            poll_count += 1
            return healthy

        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "monitor.sqlite3"
            monitor = ResearchAlertMonitor(database)
            journal = ResearchNotificationJournal(database)
            runner = ResearchMonitorRunner(monitor, poll, clock, interval_seconds=7,
                                           notification_journal=journal)
            stop = {"requested": False}
            observed = []

            def sleep(seconds):
                clock.sleep(seconds)
                if len(observed) == 3:
                    stop["requested"] = True

            for cycle in runner.run_continuously(sleep, lambda: stop["requested"]):
                observed.append(cycle)

            self.assertEqual(poll_count, 3)
            self.assertEqual([x["nextDelaySeconds"] for x in observed], [7, 7, 7])
            self.assertTrue(all(x["mode"] == "DRY_RUN" for x in observed))
            self.assertTrue(all(x["result"]["signal"] == "WAIT" for x in observed))
            self.assertTrue(all(x["executable"] is False for x in observed))
            self.assertEqual(observed[0]["notifications"]["current"]["signal"], "WAIT")
            self.assertEqual(observed[0]["notifications"]["delivery"],
                             "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
            self.assertTrue(all(x["notifications"]["events"] == [] for x in observed[1:]))
            self.assertEqual(monitor.history(), [])
            journal.close()
            monitor.close()

    def test_continuous_loop_requires_host_sleep_and_stop_callbacks(self):
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "monitor.sqlite3")
            runner = ResearchMonitorRunner(monitor, lambda: None, clock)
            with self.assertRaises(TypeError):
                list(runner.run_continuously(None, lambda: True))
            with self.assertRaises(TypeError):
                list(runner.run_continuously(clock.sleep, None))
            monitor.close()


if __name__ == "__main__":
    unittest.main()
