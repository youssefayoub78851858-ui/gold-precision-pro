import copy
import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from offline_m15_cycle import OfflineM15Cycle
from test_xauusd_research_pipeline import fixture_bundle

class RestartTests(unittest.TestCase):
    def test_restart_preserves_pending_entry_exit_and_revision_lock(self):
        p,c,now=fixture_bundle()
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            db=pathlib.Path(directory)/"synthetic-m15-rehearsal.sqlite3"
            def open_cycle():
                cycle=OfflineM15Cycle(paper_rehearsal=True,paper_database=db)
                self.addCleanup(cycle.close)
                return cycle
            def advance(p,now,**prices):
                p=copy.deepcopy(p)
                f=p["frames"]["15min"]
                bar={"openTime":now.isoformat().replace("+00:00","Z"),**prices}
                f["candles"].append(bar);f["expectedOpenTimes"].append(bar["openTime"])
                later=now+dt.timedelta(minutes=15);p["receivedUTC"]=later.isoformat()
                return p,later
            cycle=open_cycle()
            self.assertEqual(cycle.accept(p,c,now)["syntheticPending"],1)
            cycle.close()
            cycle=open_cycle()
            self.assertEqual(cycle.accept(p,c,now)["status"],"DUPLICATE_SKIPPED")
            p,now=advance(p,now,open=104,high=105,low=103,close=104)
            context={"v3Feeds":{},"r2Feeds":{},"risk":c["risk"],"spread":c["spread"]}
            self.assertEqual(cycle.accept(p,context,now)["syntheticOpen"],1)
            target=cycle.paper.summary()["position"][0]["target"]
            cycle.close()
            cycle=open_cycle()
            p,now=advance(p,now,open=104,high=target+1,low=103,close=target)
            self.assertEqual(cycle.accept(p,context,now)["syntheticClosed"],1)
            cycle.close()
            cycle=open_cycle()
            self.assertEqual(cycle.accept(p,context,now)["syntheticClosed"],1)
            changed=copy.deepcopy(p);changed["frames"]["4h"]["candles"][-1]["high"]+=1
            self.assertEqual(cycle.accept(changed,context,now)["status"],"CONFLICTING_CLOSED_HISTORY")
            cycle.close()
            cycle=open_cycle()
            self.assertEqual(cycle.accept(p,context,now)["status"],"REQUALIFICATION_REQUIRED")
            self.assertEqual(cycle.paper.summary()["trades"][0]["reason"],"TARGET")
            self.assertEqual(len(cycle.paper.summary()["trades"]),1)

    def test_explicit_test_only_and_dedicated_path_required(self):
        with tempfile.TemporaryDirectory() as directory:
            db=pathlib.Path(directory)/"synthetic-m15-rehearsal.sqlite3"
            with self.assertRaises(ValueError):
                OfflineM15Cycle(paper_database=db)
            with patch.dict("os.environ", {"GPP_SYNTHETIC_TEST_SIMULATION":"0"}):
                with self.assertRaises(ValueError):
                    OfflineM15Cycle(paper_rehearsal=True,paper_database=db)
            self.assertFalse(db.exists())

if __name__=="__main__":
    unittest.main()
