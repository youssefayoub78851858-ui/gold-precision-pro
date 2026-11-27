"""Synthetic-only supervisor adapter; uses the existing monitor and retry runner.

The caller supplies an explicit poll callback returning IDLE, OUTAGE or
a PACKET. No sockets, secrets, service launch or actual trade permission.
A missing heartbeat or overdue candle locks the rehearsal; restart is not
a means of unlocking a persisted paper account.
"""
import datetime as dt
import os
from offline_m15_cycle import OfflineM15Cycle, WIDTH
from research_monitor_runner import ResearchMonitorRunner
from xauusd_feed_gate import parse_utc

class OfflineM15Supervisor:
    def __init__(self, cycle, monitor, poll, clock, *, interval_seconds=10):
        if (os.environ.get('GPP_SYNTHETIC_TEST_SIMULATION') != '1'
                or not isinstance(cycle, OfflineM15Cycle)
                or not callable(poll) or not callable(clock)):
            raise ValueError('Explicit isolated rehearsal required')
        self.cycle, self.monitor, self.poll, self.clock = cycle, monitor, poll, clock
        self.runner = ResearchMonitorRunner(monitor, self._poll, clock,
            interval_seconds=interval_seconds, heartbeat_misses=3)

    def _result(self, state, *, failed=False):
        return dict(status='WAIT_M15_SUPERVISOR_LOCKED' if failed else 'SYNTHETIC_TEST_ONLY',
                    cycleStatus=state, sourceDataMode='synthetic', simulationOnly=True,
                    researchEligible=False, signal='WAIT', executable=False,
                    paperOrdersAllowed=False, realMarketDataConnected=False,
                    diagnostics={'alerts': {'status':'BLOCKED' if failed else 'CLEAR',
                    'items':[{'severity':'BLOCKING','code':'M15_SUPERVISOR_LOCKED',
                    'source':'m15-cycle','message':'Synthetic rehearsal requires requalification'}]
                    if failed else []}})

    def _lock(self, reason):
        if not self.cycle.blocked:
            self.cycle.lock()
        return self._result(reason, failed=True)

    def _poll(self):
        if self.cycle.blocked:
            return self._lock('REQUALIFICATION_REQUIRED')
        try:
            now = parse_utc(self.clock().isoformat())
            if (self.cycle.last_close is not None and
                now > self.cycle.last_close + WIDTH + dt.timedelta(seconds=30)):
                return self._lock('M15_CLOSE_OVERDUE')
            event = self.poll()
            if event == {'kind':'IDLE'}:
                return self._result('WAIT_NEXT_CLOSE')
            if not isinstance(event, dict) or event.get('kind') != 'PACKET':
                return self._lock('SOURCE_UNAVAILABLE')
            status = self.cycle.accept(event.get('packet'), event.get('context'), now)['status']
            if status not in ('OFFLINE_CYCLE_REVIEWED','DUPLICATE_SKIPPED'):
                return self._lock(status)
            return self._result(status)
        except Exception:
            return self._lock('CYCLE_OR_POLL_FAILED')

    def tick(self):
        # Check the persisted heartbeat BEFORE runner.tick() can invoke poll.
        # The existing monitor updates its timestamp at the beginning of tick.
        now = parse_utc(self.clock().isoformat())
        prior = self.monitor.db.execute(
            'SELECT last_heartbeat_utc FROM research_monitor_runtime WHERE id=1').fetchone()
        if prior is not None:
            delta = (now - parse_utc(prior[0])).total_seconds()
            if delta < 0:
                self.cycle.lock()
                raise ValueError('Rehearsal heartbeat clock rolled back')
            if delta > self.runner.heartbeat_timeout_seconds:
                self.cycle.lock()
        return self.runner.tick()

    def run_until_stopped(self, stop_requested, sleep):
        if not callable(stop_requested) or not callable(sleep):
            raise ValueError('Explicit stop and sleep callbacks required')
        while not stop_requested():
            result = self.tick()
            yield result
            if not stop_requested():
                sleep(result['nextDelaySeconds'])
