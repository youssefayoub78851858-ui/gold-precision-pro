"""Synthetic-only coverage, safety and parsing tests for Capital.com Demo."""
import copy
import datetime as dt
import unittest

from capital_demo_historical_batch_plan import plan_demo_closed_history
from capital_demo_offline_batch_audit import audit_disabled_history_pages

START="2026-11-16T08:00:00Z"
END="2026-11-16T12:00:00Z"
ASOF="2026-11-20T12:00:00Z"
EPIC="TEST.GOLD.EPIC"
WIDTH={"M15":900,"H1":3600,"H4":14400}


def sample():
    p=plan_demo_closed_history(EPIC,START,END,ASOF,bars_per_call=17)
    assert p["status"]=="INERT_PLAN_ONLY"
    out={}
    for frame,parts in p["requests"].items():
        out[frame]=[]
        for part in parts:
            opened=dt.datetime.fromisoformat(
                part["firstExpectedOpenUTC"].replace("Z","+00:00")
            )
            candles=[]
            for i in range(part["expectedClosedSlots"]):
                stamp=(opened+dt.timedelta(seconds=i*WIDTH[frame])).strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
                candles.append({
                    "snapshotTimeUTC":stamp,
                    "openPrice":{"bid":4000,"ask":4000.4},
                    "highPrice":{"bid":4002,"ask":4002.4},
                    "lowPrice":{"bid":3998,"ask":3998.4},
                    "closePrice":{"bid":4001,"ask":4001.4}
                })
            out[frame].append({"httpStatus":200,"response":{
                "resolution":part["request"]["query"]["resolution"],
                "epic":EPIC,"prices":candles
            }})
    return p,out


class OfflineBatchSafetyTests(unittest.TestCase):
    def wait(self,v):
        self.assertEqual(v["signal"],"WAIT")
        for name in ("executable","researchEligible","paperOrdersAllowed",
                     "liveOrdersAllowed","sourceRightsVerified",
                     "brokerCalendarVerified","pointInTimeReceiptsVerified",
                     "forwardHoldoutValidated","credentialsUsed","networkAllowed"):
            self.assertFalse(v[name], name)
        self.assertEqual(v["providerRequestsMade"],0)
        self.assertEqual(v["brokerOrdersSent"],0)

    def test_local_complete_price_geometry_cannot_authorize_trading(self):
        p,resp=sample()
        result=audit_disabled_history_pages(p,resp)
        self.wait(result)
        self.assertEqual(result["status"],"LOCAL_GEOMETRY_ONLY_NOT_ADMITTED")
        self.assertEqual(result["receivedClosedCounts"],{"M15":16,"H1":4,"H4":1})
        self.assertEqual(result["unverifiedMissingUTCGridSlots"],{"M15":0,"H1":0,"H4":0})
        self.assertEqual(result["crossFrameParityCounts"]["H4"]["fullyCoveredMatched"],1)
        self.assertEqual(result["directH4FromH1ParityCounts"]["fullyCoveredMatched"],1)
        self.assertFalse(result["observedPriceConflict"])
        self.assertTrue(result["fullUtcGridCoverage"])
        self.assertTrue(result["localCrossFrameParityFullyCovered"])
        self.assertNotIn("4000",str(result))
        self.assertNotIn("EPIC",str(result))
        self.assertNotIn("snapshotTimeUTC",str(result))
        self.assertNotIn("private",str(result).lower())

    def test_missing_slot_not_misrepresented_as_complete_calendar(self):
        p,resp=sample()
        resp["M15"][0]["response"]["prices"].pop(5)
        o=audit_disabled_history_pages(p,resp)
        self.wait(o)
        self.assertEqual(o["status"],"INCOMPLETE_OR_UNVERIFIED")
        self.assertEqual(o["unverifiedMissingUTCGridSlots"]["M15"],1)
        self.assertFalse(o["fullUtcGridCoverage"])
        self.assertFalse(o["localCrossFrameParityFullyCovered"])
        self.assertTrue(o["potentialUnexplainedMissingHistory"])

    def test_bid_ask_h4_h1_conflict_blocked(self):
        p,resp=sample()
        resp["H4"][0]["response"]["prices"][0]["highPrice"]["ask"]=4004.4
        r=audit_disabled_history_pages(p,resp)
        self.wait(r)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["reason"],"BID_ASK_CROSS_FRAME_OHLC_CONFLICT")
        self.assertTrue(r["observedPriceConflict"])

    def test_tampered_plan_rejected_before_any_parser(self):
        p,resp=sample()
        candidates=[
            lambda x:x.update(status="TRADE_READY"),
            lambda x:x.update(sourceRightsVerified=True),
            lambda x:x.update(barsPerCall=1000),
            lambda x:x.update(endExclusiveUTC="2026-11-17T00:00:00Z"),
            lambda x:x["requests"]["M15"][0]["request"].update(
                baseUrl="https://api-capital.backend-capital.com"),
            lambda x:x["requests"]["M15"][0]["request"].update(method="POST"),
            lambda x:x["requests"]["M15"][0]["request"].update(enabled=True),
            lambda x:x["requests"]["M15"][0]["request"]["query"].update(
                apiKey="SECRET")
        ]
        for fn in candidates:
            with self.subTest(fn=str(fn)):
                bad=copy.deepcopy(p);fn(bad)
                r=audit_disabled_history_pages(bad,resp)
                self.wait(r)
                self.assertEqual(r["status"],"BLOCKED")
                self.assertNotIn("SECRET",str(r))

    def test_no_out_of_window_duplicate_future_candle_or_trading_api(self):
        variants=[
            (lambda p,r:r["M15"][0]["response"]["prices"].append(
                copy.deepcopy(r["M15"][0]["response"]["prices"][-1])),
             "DUPLICATE_OR_REORDERED_BROKER_HISTORY"),
            (lambda p,r:r["M15"][0]["response"]["prices"][-1].update(
                snapshotTimeUTC="2026-11-16T12:00:00"),
             "OUT_OF_EXPECTED_CANDLE_WINDOW"),
            (lambda p,r:r["M15"][0]["response"]["prices"][0].update(
                snapshotTimeUTC="2026-11-16T07:45:00"),
             "OUT_OF_EXPECTED_CANDLE_WINDOW"),
            (lambda p,r:r["M15"][0]["response"]["prices"].reverse(),
             "DUPLICATE_OR_REORDERED_BROKER_HISTORY"),
            (lambda p,r:r["M15"][0].update(httpStatus=401),
             "HTTP_NOT_VERIFIED_SUCCESS"),
            (lambda p,r:r["M15"][0]["response"].update(epic="WRONG.EPIC"),
             "BROKER_EPIC_MISMATCH"),
            (lambda p,r:r["M15"][0]["response"].update(resolution="HOUR"),
             "BROKER_RESOLUTION_MISMATCH"),
            (lambda p,r:r["M15"][0]["response"]["prices"][0]["openPrice"].update(
                ask=3999),
             "UNTRUSTED_OR_INVALID_OFFLINE_BATCH_DATA"),
            (lambda p,r:r["M15"][0]["response"]["prices"][0]["openPrice"].update(
                bid=float("nan")),
             "UNTRUSTED_OR_INVALID_OFFLINE_BATCH_DATA")
        ]
        for fn,reason in variants:
            with self.subTest(reason=reason):
                p,resp=sample();fn(p,resp)
                o=audit_disabled_history_pages(p,resp)
                self.wait(o)
                self.assertEqual(o["status"],"BLOCKED",o)
                self.assertEqual(o["reason"],reason,o)

    def test_missing_pages_or_invalid_wrapper_fail_closed(self):
        for mutate in (
            lambda p,r:r.pop("H4"),
            lambda p,r:r["H4"].clear(),
            lambda p,r:r["M15"].append({"httpStatus":200,"response":{"prices":[]}}),
            lambda p,r:r["M15"][0].update(secret="NEVER_ECHO"),
        ):
            p,resp=sample();mutate(p,resp)
            v=audit_disabled_history_pages(p,resp)
            self.wait(v);self.assertEqual(v["status"],"BLOCKED")
            self.assertNotIn("NEVER_ECHO",str(v))
        for plan,pages in ((None,None),({},{}),("bad",[])):
            v=audit_disabled_history_pages(plan,pages)
            self.wait(v);self.assertEqual(v["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
