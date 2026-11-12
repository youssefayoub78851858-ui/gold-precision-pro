"""Finite-cycle, offline runner around the local ResearchAlertMonitor.

The runner accepts injected clock, poll and sleep functions, so tests can model
outages and recovery without wall-clock waits, network clients, or providers.
It refuses non-synthetic observations and preserves WAIT/non-execution.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable

from research_monitor import ResearchAlertMonitor
from research_notification import ResearchNotificationJournal
from xauusd_feed_gate import parse_utc, retry_delay_seconds


class ResearchMonitorRunner:
    def __init__(self, monitor: ResearchAlertMonitor, poll: Callable[[], dict | None],
                 clock: Callable[[], dt.datetime], *, interval_seconds: int = 15,
                 heartbeat_misses: int = 2, retry_base_seconds: int = 5,
                 retry_max_seconds: int = 300,
                 notification_journal: ResearchNotificationJournal | None = None):
        if interval_seconds < 1 or heartbeat_misses < 1:
            raise ValueError("positive monitor interval and heartbeat threshold required")
        self.monitor = monitor
        self.poll = poll
        self.clock = clock
        self.interval_seconds = interval_seconds
        self.heartbeat_timeout_seconds = interval_seconds * heartbeat_misses
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.notification_journal = notification_journal
        self.failure_count = 0

    def tick(self) -> dict:
        now = parse_utc(self.clock().isoformat())
        heartbeat_gap = self.monitor.heartbeat_gap_seconds(now)
        poll_error = False
        try:
            result = self.poll()
        except Exception as error:  # convert every service fault into a fail-closed observation
            poll_error = True
            result = {"status": "WAIT_ENGINE_FAILURE", "sourceDataMode": "synthetic",
                      "researchEligible": False, "signal": "WAIT", "executable": False,
                      "reason": f"Research poll failed: {type(error).__name__}"}

        result, contract_error = self._quarantine(result)
        if heartbeat_gap is not None and heartbeat_gap > self.heartbeat_timeout_seconds:
            diagnostics = result.setdefault("diagnostics", {})
            alerts = diagnostics.setdefault("alerts", {"status": "BLOCKED", "items": []})
            alerts["status"] = "BLOCKED"
            alerts.setdefault("items", []).append({
                "severity": "BLOCKING", "code": "MONITOR_HEARTBEAT_MISSED",
                "source": "monitor", "message": f"Monitor heartbeat gap was {heartbeat_gap:g} seconds",
            })

        status = result.get("status") if isinstance(result, dict) else None
        intake_blocked = (result.get("intake") or {}).get("status") == "BLOCKED"
        alert_blocked = ((result.get("diagnostics") or {}).get("alerts") or {}).get("status") == "BLOCKED"
        failed = poll_error or contract_error or (isinstance(status, str) and status.startswith("WAIT_")) or intake_blocked or alert_blocked
        if failed:
            self.failure_count += 1
            delay = retry_delay_seconds(self.failure_count, self.retry_base_seconds, self.retry_max_seconds)
        else:
            self.failure_count = 0
            delay = self.interval_seconds

        observed = self.monitor.observe(result, now)
        notifications = (self.notification_journal.observe(result, now)
                         if self.notification_journal is not None else None)
        output = {"observedUTC": now.isoformat().replace("+00:00", "Z"),
                "result": result, "alerts": observed,
                "failureCount": self.failure_count, "nextDelaySeconds": delay,
                "signal": "WAIT", "executable": False}
        if notifications is not None:
            output["notifications"] = notifications
        return output

    @staticmethod
    def _quarantine(result: dict | None) -> tuple[dict, bool]:
        if result is None:
            return {"status": "WAIT_PIPELINE_UNAVAILABLE", "sourceDataMode": "synthetic",
                    "researchEligible": False, "signal": "WAIT", "executable": False,
                    "reason": "No pipeline observation received"}, False
        valid = (isinstance(result, dict)
                 and result.get("sourceDataMode") == "synthetic"
                 and result.get("signal") == "WAIT"
                 and result.get("executable") is False
                 and result.get("researchEligible") is False)
        if not valid:
            return {"status": "WAIT_MONITOR_CONTRACT_VIOLATION", "sourceDataMode": "synthetic",
                    "researchEligible": False, "signal": "WAIT", "executable": False,
                    "diagnostics": {"alerts": {"status": "BLOCKED", "items": [{
                        "severity": "BLOCKING", "code": "MONITOR_CONTRACT_VIOLATION",
                        "source": "monitor", "message": "Only quarantined synthetic WAIT observations are accepted",
                    }]}}}, True
        if result.get("status") == "SYNTHETIC_TEST_ONLY" and result.get("simulationOnly") is not True:
            result = {**result, "status": "WAIT_SYNTHETIC_QUARANTINED",
                      "reason": "Synthetic data without isolated-test opt-in cannot be treated as healthy evidence"}
            return result, True
        return result, False

    def run(self, cycles: int, sleep: Callable[[float], None]) -> list[dict]:
        """Run a finite schedule; caller injects sleep to keep timing controllable."""
        if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 1:
            raise ValueError("cycles must be a positive integer")
        if not callable(sleep):
            raise TypeError("an injected sleep function is required")
        results = []
        for index in range(cycles):
            result = self.tick()
            results.append(result)
            if index + 1 < cycles:
                sleep(result["nextDelaySeconds"])
        return results

    def run_continuously(self, sleep: Callable[[float], None],
                         stop_requested: Callable[[], bool]):
        """Yield each DRY_RUN observation until the host requests a stop.

        Sleep and shutdown are injected so a service wrapper can use an
        interruptible Event.wait while tests advance simulated time. Results
        are yielded one at a time; a 24/7 caller does not accumulate an
        unbounded in-memory history. The host remains responsible for process
        supervision and persistent storage.
        """
        if not callable(sleep) or not callable(stop_requested):
            raise TypeError("continuous runner requires injected sleep and stop callbacks")
        while not stop_requested():
            result = self.tick()
            result["mode"] = "DRY_RUN"
            yield result
            if not stop_requested():
                sleep(result["nextDelaySeconds"])
