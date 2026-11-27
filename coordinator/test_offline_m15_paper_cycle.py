import copy
import datetime as dt
import unittest
from unittest.mock import patch
from test_xauusd_research_pipeline import fixture_bundle
from offline_m15_cycle import OfflineM15Cycle

class PaperCycle(unittest.TestCase):
    def advance(self,p,now,**prices):
        p=copy.deepcopy(p)
        f=p["frames"]["15min"]
        bar={"openTime":now.isoformat().replace("+00:00","Z"),**prices}
        f["candles"].append(bar)
        f["expectedOpenTimes"].append(bar["openTime"])
        later=now+dt.timedelta(minutes=15)
        p["receivedUTC"]=later.isoformat()
        return p,later

    def test_requires_test_flag_and_default_does_not_open_ledger(self):
        with patch.dict("os.environ",{"GPP_SYNTHETIC_TEST_SIMULATION":"0"}):
            with self.assertRaises(ValueError):
                OfflineM15Cycle(paper_rehearsal=True)
        self.assertIsNone(OfflineM15Cycle().paper)

    def test_real_engines_to_paper_entry_exit_and_idempotence(self):
        p,c,now=fixture_bundle()
        with patch.dict("os.environ",{"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            cycle=OfflineM15Cycle(paper_rehearsal=True)
            self.addCleanup(cycle.close)
            first=cycle.accept(p,c,now)
            self.assertEqual(first["status"],"OFFLINE_CYCLE_REVIEWED")
            self.assertEqual(first["syntheticPending"],1)
            self.assertFalse(first["paperOrdersAllowed"])
            self.assertEqual(cycle.accept(p,c,now)["status"],"DUPLICATE_SKIPPED")
            p,now=self.advance(p,now,open=104,high=105,low=103,close=104)
            context={"v3Feeds":{},"r2Feeds":{},"risk":c["risk"],"spread":c["spread"]}
            second=cycle.accept(p,context,now)
            self.assertEqual(second["syntheticOpen"],1)
            pos=cycle.paper.summary()["position"][0]
            p,now=self.advance(p,now,open=104,high=pos["target"]+1,low=103,close=pos["target"])
            third=cycle.accept(p,context,now)
            self.assertEqual(third["syntheticClosed"],1)
            self.assertEqual(third["syntheticOpen"],0)
            self.assertEqual(third["signal"],"WAIT")
            self.assertFalse(third["executable"])
            self.assertEqual(cycle.accept(p,context,now)["syntheticClosed"],1)
            self.assertEqual(cycle.paper.summary()["trades"][0]["reason"],"TARGET")

    def test_disagreement_and_late_decision_never_create_pending(self):
        p,c,now=fixture_bundle()
        c=copy.deepcopy(c)
        c["v3Feeds"]["DXY"]["value"]=101
        with patch.dict("os.environ",{"GPP_SYNTHETIC_TEST_SIMULATION":"1"}):
            cycle=OfflineM15Cycle(paper_rehearsal=True)
            self.addCleanup(cycle.close)
            self.assertEqual(cycle.accept(p,c,now)["syntheticPending"],0)
            late=OfflineM15Cycle(paper_rehearsal=True)
            self.addCleanup(late.close)
            self.assertEqual(late.accept(p,c,now+dt.timedelta(seconds=1))["status"],
                             "SYNTHETIC_PAPER_REQUALIFICATION_REQUIRED")
            self.assertEqual(late.paper.summary()["pending"],[])

if __name__=="__main__":
    unittest.main()
