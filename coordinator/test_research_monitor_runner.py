"""Deterministic monitoring cycles; all observations are synthetic fixtures."""
import datetime as dt
import pathlib
import tempfile
import unittest

from research_monitor import ResearchAlertMonitor
from research_monitor_runner import ResearchMonitorRunner


class SimulatedClock:
    def __init__(self):
        self.now = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += dt.timedelta(seconds=seconds)


def healthy_synthetic():
    return {"status": "SYNTHETIC_TEST_ONLY", "sourceDataMode": "synthetic",
            "simulationOnly": True, "researchEligible": False,
            "signal": "WAIT", "executable": False,
            "intake": {"status": "SYNTHETIC_TEST_ONLY",
                       "blockingReasons": ["SYNTHETIC_DATA_NOT_REAL_MARKET_EVIDENCE"]},
            "diagnostics": {"alerts": {"status": "CLEAR", "items": []}}}


class ResearchMonitorRunnerTests(unittest.TestCase):
    def test_outage_heartbeat_gap_stale_retry_recovery_and_restart(self):
        outage = None
        stale = {"status": "WAIT_INTAKE_BLOCKED", "sourceDataMode": "synthetic",
                 "researchEligible": False, "signal": "WAIT", "executable": False,
                 "intake": {"status": "BLOCKED", "blockingReasons": [
                     "15MIN_REJECTED:15min latest closed candle is stale"]}}
        poll_results = iter([outage, stale, healthy_synthetic(), healthy_synthetic()])
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "watch.sqlite3"
            monitor = ResearchAlertMonitor(database)
            runner = ResearchMonitorRunner(monitor, lambda: next(poll_results), clock,
                                           interval_seconds=10, heartbeat_misses=2,
                                           retry_base_seconds=5, retry_max_seconds=40)
            sleeps = []

            def simulated_sleep(seconds):
                sleeps.append(seconds)
                # Model a stopped process after the first retry wait; no wall-clock sleep.
                clock.advance(seconds + (25 if len(sleeps) == 1 else 0))

            cycles = runner.run(3, simulated_sleep)
            self.assertEqual([x["nextDelaySeconds"] for x in cycles], [10, 20, 10])
            self.assertEqual(cycles[0]["result"]["signal"], "WAIT")
            self.assertFalse(cycles[0]["result"]["executable"])
            self.assertTrue(any(x["code"] == "PIPELINE_UNAVAILABLE" and x["transition"] == "RAISED"
                                for x in cycles[0]["alerts"]["events"]))
            self.assertTrue(any(x["code"] == "DATA_STALE_OR_FUTURE" for x in cycles[1]["alerts"]["events"]))
            self.assertTrue(any(x["code"] == "MONITOR_HEARTBEAT_MISSED" and x["transition"] == "RAISED"
                                for x in cycles[1]["alerts"]["events"]))
            self.assertTrue(any(x["code"] == "PIPELINE_UNAVAILABLE" and x["transition"] == "RECOVERED"
                                for x in cycles[1]["alerts"]["events"]))
            self.assertTrue(any(x["code"] == "DATA_STALE_OR_FUTURE" and x["transition"] == "RECOVERED"
                                for x in cycles[2]["alerts"]["events"]))
            self.assertTrue(any(x["code"] == "MONITOR_HEARTBEAT_MISSED" and x["transition"] == "RECOVERED"
                                for x in cycles[2]["alerts"]["events"]))
            self.assertEqual(cycles[2]["failureCount"], 0)
            self.assertEqual(cycles[2]["result"]["researchEligible"], False)
            self.assertEqual(cycles[2]["result"]["signal"], "WAIT")
            self.assertFalse(cycles[2]["result"]["executable"])
            self.assertEqual(cycles[2]["alerts"]["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
            monitor.close()

            monitor = ResearchAlertMonitor(database)
            runner = ResearchMonitorRunner(monitor, lambda: next(poll_results), clock,
                                           interval_seconds=10, heartbeat_misses=2)
            duplicate = runner.tick()
            self.assertEqual(duplicate["alerts"]["events"], [])
            self.assertEqual(duplicate["result"]["signal"], "WAIT")
            self.assertFalse(duplicate["result"]["executable"])
            monitor.close()

    def test_synthetic_without_test_quarantine_and_non_wait_contract_fail_closed(self):
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "watch.sqlite3")
            unquarantined = {**healthy_synthetic(), "simulationOnly": False}
            runner = ResearchMonitorRunner(monitor, lambda: unquarantined, clock)
            result = runner.tick()
            self.assertEqual(result["result"]["status"], "WAIT_SYNTHETIC_QUARANTINED")
            self.assertFalse(result["result"]["researchEligible"])
            self.assertEqual(result["result"]["signal"], "WAIT")
            self.assertFalse(result["result"]["executable"])
            self.assertEqual(result["failureCount"], 1)
            self.assertTrue(any(x["code"] == "SYNTHETIC_QUARANTINED" for x in result["alerts"]["events"]))

            unsafe = {**healthy_synthetic(), "signal": "BUY", "executable": True}
            unsafe_runner = ResearchMonitorRunner(monitor, lambda: unsafe, clock)
            blocked = unsafe_runner.tick()
            self.assertEqual(blocked["result"]["signal"], "WAIT")
            self.assertFalse(blocked["result"]["executable"])
            self.assertFalse(blocked["result"]["researchEligible"])
            self.assertEqual(blocked["result"]["status"], "WAIT_MONITOR_CONTRACT_VIOLATION")
            monitor.close()

    def test_engine_exception_is_wait_and_uses_bounded_retry(self):
        def failed_poll():
            raise TimeoutError("fixture service unavailable")

        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "watch.sqlite3")
            runner = ResearchMonitorRunner(monitor, failed_poll, clock,
                                           retry_base_seconds=5, retry_max_seconds=12)
            result = runner.tick()
            self.assertEqual(result["result"]["status"], "WAIT_ENGINE_FAILURE")
            self.assertEqual(result["result"]["signal"], "WAIT")
            self.assertFalse(result["result"]["executable"])
            self.assertEqual(result["nextDelaySeconds"], 10)
            self.assertEqual(result["alerts"]["events"][0]["code"], "ENGINE_UNAVAILABLE")
            monitor.close()

    def test_active_outage_does_not_repeat_after_runner_and_database_restart(self):
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "watch.sqlite3"
            monitor = ResearchAlertMonitor(database)
            first_runner = ResearchMonitorRunner(monitor, lambda: None, clock)
            first = first_runner.tick()
            self.assertEqual([x["transition"] for x in first["alerts"]["events"]], ["RAISED"])
            monitor.close()

            clock.advance(1)
            monitor = ResearchAlertMonitor(database)
            restarted_runner = ResearchMonitorRunner(monitor, lambda: None, clock)
            replay = restarted_runner.tick()
            self.assertEqual(replay["alerts"]["events"], [])
            self.assertEqual(len(monitor.history()), 1)
            monitor.close()

    def test_finite_schedule_requires_injected_simulated_sleep(self):
        clock = SimulatedClock()
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "watch.sqlite3")
            runner = ResearchMonitorRunner(monitor, healthy_synthetic, clock)
            with self.assertRaises(TypeError):
                runner.run(2, None)
            monitor.close()


if __name__ == "__main__":
    unittest.main()
