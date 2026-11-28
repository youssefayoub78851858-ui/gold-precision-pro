import copy
import unittest
from massive_synthetic_cutover import inspect_cutover
from massive_bbo_history_adapter import _aggregate
from test_massive_history_stream_parity import paired,create_quotes

class CutoverTests(unittest.TestCase):
    def windows(self):
        rest,stream=paired(create_quotes())
        # Extend the fixture with deterministic synthetic bars outside the
        # real cross-language 16-bar overlap. No real prices are used.
        import datetime as dt
        for obj,keys,offset in ((rest,("bidFrames","askFrames","midFrames"),-1),
                                (stream,("bidFrames","askFrames","frames"),1)):
            for key in keys:
                rows=obj[key]["M15"]
                bar=dict(rows[0 if offset<0 else -1])
                stamp=dt.datetime.fromisoformat(bar["openTime"].replace("Z","+00:00"))+dt.timedelta(minutes=15*offset)
                bar["openTime"]=stamp.isoformat().replace("+00:00","Z")
                if offset<0:rows.insert(0,bar)
                else:rows.append(bar)
                rows[:]=[{**r,"openTime":dt.datetime.fromisoformat(r["openTime"].replace("Z","+00:00")).isoformat().replace("+00:00","Z")} for r in rows]
                for tf,n in (("H1",4),("H4",16)):obj[key][tf]=_aggregate(rows,n)
        return rest,stream

    def test_cutover_counts_only_and_no_real_admission(self):
        old,new=self.windows()
        r=inspect_cutover(old,new)
        self.assertEqual(r["status"],"SYNTHETIC_CUTOVER_REHEARSED")
        self.assertEqual(r["overlapM15"],16)
        self.assertEqual(r["syntheticUnionM15"],18)
        self.assertEqual(r["syntheticUnionH4"],1)
        self.assertFalse(r["historyMayMergeWithStream"])
        self.assertFalse(r["paperOrdersAllowed"])

    def test_mismatch_and_unverified_modes_rejected(self):
        old,new=self.windows()
        changed=copy.deepcopy(new)
        changed["askFrames"]["M15"][5]["high"]+=1
        for tf,n in (("H1",4),("H4",16)):
            changed["askFrames"][tf]=_aggregate(changed["askFrames"]["M15"],n)
        self.assertEqual(inspect_cutover(old,changed)["status"],"BLOCKED")
        changed=copy.deepcopy(new);changed["sourceDataMode"]="live"
        self.assertEqual(inspect_cutover(old,changed)["status"],"BLOCKED")
        old,new=paired(create_quotes())
        self.assertEqual(inspect_cutover(old,new)["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
