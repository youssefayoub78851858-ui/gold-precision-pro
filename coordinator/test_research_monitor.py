"""Offline alert state/recovery tests using synthetic-only observations."""
import datetime as dt
import pathlib
import tempfile
import unittest

from research_monitor import ResearchAlertMonitor


NOW = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)


def healthy_fixture():
    return {"status": "SYNTHETIC_TEST_ONLY", "sourceDataMode": "synthetic",
            "simulationOnly": True, "researchEligible": False, "signal": "WAIT",
            "executable": False, "intake": {"blockingReasons": ["SYNTHETIC_DATA_NOT_REAL_MARKET_EVIDENCE"]},
            "diagnostics": {"alerts": {"status": "CLEAR", "items": []}}}


class ResearchMonitorTests(unittest.TestCase):
    def test_outage_duplicate_restart_recovery_and_reopen_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "research-alerts.sqlite3"
            outage = {"status": "WAIT_ENGINE_FAILURE", "sourceDataMode": "synthetic",
                      "signal": "WAIT", "executable": False,
                      "reason": "Node research engine unavailable"}
            monitor = ResearchAlertMonitor(database)
            first = monitor.observe(outage, NOW)
            self.assertEqual([x["transition"] for x in first["events"]], ["RAISED"])
            self.assertEqual(first["events"][0]["code"], "ENGINE_UNAVAILABLE")
            self.assertEqual(monitor.observe(outage, NOW)["events"], [])
            monitor.close()

            monitor = ResearchAlertMonitor(database)
            replay = monitor.observe(outage, NOW)
            self.assertEqual(replay["events"], [])
            recovered = monitor.observe(healthy_fixture(), NOW + dt.timedelta(minutes=1))
            self.assertEqual([x["transition"] for x in recovered["events"]], ["RECOVERED"])
            self.assertEqual(monitor.observe(healthy_fixture(), NOW + dt.timedelta(minutes=2))["events"], [])
            reopened = monitor.observe(outage, NOW + dt.timedelta(minutes=3))
            self.assertEqual([x["transition"] for x in reopened["events"]], ["REOPENED"])
            self.assertEqual(len(monitor.history()), 3)
            self.assertEqual(reopened["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
            self.assertEqual(reopened["signal"], "WAIT")
            self.assertFalse(reopened["executable"])
            monitor.close()

    def test_stale_gap_and_unclosed_candle_alert_codes(self):
        result = {"status": "WAIT_INTAKE_BLOCKED", "sourceDataMode": "synthetic",
                  "signal": "WAIT", "executable": False,
                  "intake": {"blockingReasons": [
                      "M15_REJECTED:15min latest closed candle is stale",
                      "H1_REJECTED:1h candle gap: missing schedule row",
                      "H4_REJECTED:forming or future 4h candle",
                  ]}}
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "alerts.sqlite3")
            observed = monitor.observe(result, NOW)
            self.assertEqual({x["code"] for x in observed["events"]},
                             {"DATA_STALE_OR_FUTURE", "DATA_GAP_OR_MISSING", "CANDLE_UNCLOSED"})
            self.assertEqual(observed["signal"], "WAIT")
            self.assertFalse(observed["executable"])
            monitor.close()

    def test_conflict_and_risk_blockers_are_local_deduplicated_alerts(self):
        result = {"status": "SYNTHETIC_TEST_ONLY", "sourceDataMode": "synthetic",
                  "simulationOnly": True, "researchEligible": False,
                  "signal": "WAIT", "executable": False,
                  "diagnostics": {"alerts": {"items": [
                      {"severity": "BLOCKING", "code": "ANALYSIS_CONFLICT", "source": "DXY",
                       "message": "Independent evidence disagrees"},
                      {"severity": "BLOCKING", "code": "RISK_GATE_BLOCKED", "source": "risk",
                       "message": "Kill switch active"},
                  ]}}}
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "alerts.sqlite3")
            first = monitor.observe(result, NOW)
            second = monitor.observe(result, NOW + dt.timedelta(seconds=15))
            self.assertEqual(len(first["events"]), 2)
            self.assertEqual(second["events"], [])
            self.assertEqual(first["delivery"], "LOCAL_AUDIT_ONLY_NO_EXTERNAL_SEND")
            monitor.close()

    def test_missing_monitor_observation_is_an_outage_and_recovers_once(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = ResearchAlertMonitor(pathlib.Path(directory) / "alerts.sqlite3")
            first = monitor.observe(None, NOW)
            self.assertEqual(first["events"][0]["code"], "PIPELINE_UNAVAILABLE")
            self.assertEqual(monitor.observe(None, NOW)["events"], [])
            recovered = monitor.observe(healthy_fixture(), NOW + dt.timedelta(minutes=1))
            self.assertEqual([x["transition"] for x in recovered["events"]], ["RECOVERED"])
            monitor.close()


if __name__ == "__main__":
    unittest.main()
