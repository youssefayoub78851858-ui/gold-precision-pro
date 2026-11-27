import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from offline_m15_cycle import OfflineM15Cycle
from offline_m15_supervisor import OfflineM15Supervisor
from research_monitor import ResearchAlertMonitor
from test_xauusd_research_pipeline import fixture_bundle

class SupervisorTests(unittest.TestCase):
    def test_outage_cancels_pending_and_deduplicates_after_restart(self):
        p,c,instant=fixture_bundle()
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ",{"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            base=pathlib.Path(directory)
            db=base/"synthetic-m15-rehearsal.sqlite3"
            alerts=base/"monitor.sqlite3"
            cycle=OfflineM15Cycle(paper_rehearsal=True,paper_database=db)
            monitor=ResearchAlertMonitor(alerts)
            clock=[instant]
            events=iter([dict(kind="PACKET",packet=p,context=c),{"kind":"IDLE"},{"kind":"OUTAGE"}])
            sup=OfflineM15Supervisor(cycle,monitor,lambda:next(events),lambda:clock[0])
            try:
                first=sup.tick()
                self.assertEqual(first["result"]["cycleStatus"],"OFFLINE_CYCLE_REVIEWED")
                self.assertEqual(cycle.report("TEST")["syntheticPending"],1)
                clock[0]+=dt.timedelta(seconds=10)
                self.assertEqual(sup.tick()["result"]["cycleStatus"],"WAIT_NEXT_CLOSE")
                clock[0]+=dt.timedelta(seconds=10)
                failure=sup.tick()
                self.assertEqual(failure["result"]["cycleStatus"],"SOURCE_UNAVAILABLE")
                self.assertEqual(cycle.report("TEST")["syntheticPending"],0)
                self.assertEqual([x["code"] for x in failure["alerts"]["events"]],["M15_SUPERVISOR_LOCKED"])
                self.assertEqual(failure["failureCount"],1)
                clock[0]+=dt.timedelta(seconds=10)
                self.assertEqual(sup.tick()["alerts"]["events"],[])
            finally:
                cycle.close();monitor.close()
            cycle=OfflineM15Cycle(paper_rehearsal=True,paper_database=db)
            monitor=ResearchAlertMonitor(alerts)
            try:
                clock[0]+=dt.timedelta(seconds=10)
                sup=OfflineM15Supervisor(cycle,monitor,lambda: self.fail("locked must not poll"),lambda:clock[0])
                result=sup.tick()
                self.assertEqual(result["alerts"]["events"],[])
                self.assertEqual(result["signal"],"WAIT")
                self.assertFalse(result["executable"])
                self.assertEqual(result["result"]["cycleStatus"],"REQUALIFICATION_REQUIRED")
            finally:
                cycle.close();monitor.close()

    def test_missed_heartbeat_stops_before_poll_and_stop_callback(self):
        p,c,instant=fixture_bundle()
        with patch.dict("os.environ",{"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            cycle=OfflineM15Cycle(paper_rehearsal=True)
            monitor=ResearchAlertMonitor(":memory:")
            self.addCleanup(cycle.close);self.addCleanup(monitor.close)
            clock=[instant]
            events=iter([dict(kind="PACKET",packet=p,context=c)])
            sup=OfflineM15Supervisor(cycle,monitor,lambda:next(events),lambda:clock[0])
            self.assertEqual(sup.tick()["result"]["cycleStatus"],"OFFLINE_CYCLE_REVIEWED")
            clock[0]+=dt.timedelta(seconds=31)
            result=sup.tick()
            self.assertTrue(cycle.blocked)
            self.assertEqual(cycle.calls,1)
            self.assertEqual(cycle.report("TEST")["syntheticPending"],0)
            self.assertTrue(any(x["code"]=="MONITOR_HEARTBEAT_MISSED" for x in result["alerts"]["events"]))
            self.assertEqual(list(sup.run_until_stopped(lambda:True,lambda _:self.fail("no sleep"))),[])

if __name__=="__main__":
    unittest.main()
