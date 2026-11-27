import copy
import datetime as dt
import unittest
from unittest.mock import patch
from test_xauusd_research_pipeline import fixture_bundle
from offline_m15_cycle import OfflineM15Cycle

class M15CycleTests(unittest.TestCase):
    def test_actual_engines_once_and_no_duplicate(self):
        p,c,now=fixture_bundle()
        cycle=OfflineM15Cycle()
        with patch.dict("os.environ", {"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            result=cycle.accept(p,c,now)
            self.assertEqual(result["status"],"OFFLINE_CYCLE_REVIEWED")
            self.assertTrue(result["enginesReviewed"])
            self.assertEqual(result["signal"],"WAIT")
            self.assertFalse(result["paperOrdersAllowed"])
            self.assertEqual(cycle.accept(p,c,now)["status"],"DUPLICATE_SKIPPED")
            changed=copy.deepcopy(p)
            changed["frames"]["15min"]["candles"][-1]["high"]+=1
            self.assertEqual(cycle.accept(changed,c,now)["status"],"CONFLICTING_CLOSED_HISTORY")
            self.assertEqual(cycle.accept(p,c,now)["status"],"REQUALIFICATION_REQUIRED")
            self.assertEqual(cycle.calls,1)

    def test_stale_unlicensed_and_gap_cannot_trigger(self):
        p,c,now=fixture_bundle()
        cycle=OfflineM15Cycle()
        self.assertEqual(cycle.accept({**p,"mode":"live"},c,now)["status"],"SYNTHETIC_ONLY")
        self.assertEqual(cycle.accept(p,c,now+dt.timedelta(seconds=31))["status"],"NOT_FRESH_M15_CLOSE")
        self.assertEqual(cycle.calls,0)
        with patch.dict("os.environ", {"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            cycle.accept(p,c,now)
        later=copy.deepcopy(p)
        for f in later["frames"].values():
            for row in f["candles"]:
                row["openTime"]=(dt.datetime.fromisoformat(row["openTime"].replace("Z","+00:00"))+dt.timedelta(hours=4)).isoformat()
            f["expectedOpenTimes"]=[x["openTime"] for x in f["candles"]]
        later_now=now+dt.timedelta(hours=4)
        later["receivedUTC"]=later_now.isoformat()
        self.assertEqual(cycle.accept(later,c,later_now)["status"],"GAP_OR_REVERSED_CLOSE")
        self.assertEqual(cycle.calls,1)


    def test_higher_frame_revision_same_close_and_next_close_blocks(self):
        p,c,now=fixture_bundle()
        with patch.dict("os.environ", {"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            for interval in ("1h","4h"):
                cycle=OfflineM15Cycle()
                self.assertEqual(cycle.accept(p,c,now)["status"],"OFFLINE_CYCLE_REVIEWED")
                changed=copy.deepcopy(p)
                changed["frames"][interval]["candles"][-1]["high"]+=1
                self.assertEqual(cycle.accept(changed,c,now)["status"],"CONFLICTING_CLOSED_HISTORY")
                self.assertEqual(cycle.calls,1)

            cycle=OfflineM15Cycle(paper_rehearsal=True)
            self.addCleanup(cycle.close)
            self.assertEqual(cycle.accept(p,c,now)["syntheticPending"],1)
            changed=copy.deepcopy(p)
            changed["frames"]["4h"]["candles"][-1]["high"]+=1
            frame=changed["frames"]["15min"]
            opened=now.isoformat().replace("+00:00","Z")
            frame["candles"].append(dict(openTime=opened,open=104,high=105,low=103,close=104))
            frame["expectedOpenTimes"].append(opened)
            later=now+dt.timedelta(minutes=15)
            changed["receivedUTC"]=later.isoformat()
            blocked=cycle.accept(changed,c,later)
            self.assertEqual(blocked["status"],"CONFLICTING_CLOSED_HISTORY")
            self.assertEqual(blocked["syntheticPending"],0)
            self.assertEqual(blocked["syntheticOpen"],0)
            self.assertEqual(cycle.calls,1)

if __name__=="__main__":
    unittest.main()
