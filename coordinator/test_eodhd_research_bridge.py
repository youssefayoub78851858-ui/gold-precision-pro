"""EODHD private snapshot to existing research gate: offline negative-path tests."""
import datetime as dt
import copy
import unittest
from unittest.mock import patch

from eodhd_research_bridge import IndependentEvidence, review_eodhd_snapshot
from xauusd_feed_gate import SourcePolicy

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,12,17,0,3,tzinfo=UTC)

def sample(count=16):
    # Explicitly fabricated OHLC, no provider data, no license evidence.
    end=dt.datetime(2026,11,12,17,0,0,tzinfo=UTC)
    start=end-dt.timedelta(minutes=count*15)
    times=[]
    for n in range(count):
        t=start+dt.timedelta(minutes=15*n)
        base=3900+n*.01
        times.append((
            {"openTime":t.isoformat().replace("+00:00","Z"),
             "open":base+.25,"high":base+1.25,"low":base-.75,"close":base+.75},
            {"openTime":t.isoformat().replace("+00:00","Z"),
             "open":base,"high":base+1,"low":base-1,"close":base+.5},
            {"openTime":t.isoformat().replace("+00:00","Z"),
             "open":base+.5,"high":base+1.5,"low":base-.5,"close":base+1.0},
        ))
    def aggregate(rows,num):
        out=[]
        step=dt.timedelta(minutes=15*num)
        data={dt.datetime.fromisoformat(x["openTime"].replace("Z","+00:00")):x for x in rows}
        first=dt.datetime.fromtimestamp((int(start.timestamp())//(900*num))*(900*num),UTC)
        p=first
        while p+step<=end:
            group=[data.get(p+dt.timedelta(minutes=15*i)) for i in range(num)]
            if all(group):
                out.append({"openTime":p.isoformat().replace("+00:00","Z"),"open":group[0]["open"],
                            "high":max(x["high"] for x in group),"low":min(x["low"] for x in group),
                            "close":group[-1]["close"]})
            p+=step
        return out
    m=[x[0] for x in times];b=[x[1] for x in times];a=[x[2] for x in times]
    return {"provider":"EODHD","instrument":"XAU/USD","quoteType":"INDICATIVE_MIDQUOTE_OHLC",
            "mode":"REVIEW_ONLY","signal":"WAIT","executable":False,"researchEligible":False,
            "readyForTrading":False,"sessionVerified":False,"indicatorWarmupReady":False,
            "latestQuote":{"bid":4000,"ask":4001,"timeUTC":(NOW-dt.timedelta(seconds=2)).isoformat()},
            "frames":{"M15":m,"H1":aggregate(m,4),"H4":aggregate(m,16)},
            "bidFrames":{"M15":b,"H1":aggregate(b,4),"H4":aggregate(b,16)},
            "askFrames":{"M15":a,"H1":aggregate(a,4),"H4":aggregate(a,16)}}

class EodhdResearchStaging(unittest.TestCase):
    def review(self, data, **kwargs):
        with patch("eodhd_research_bridge.run_research_pipeline", side_effect=AssertionError("never call engine in blocked review")):
            return review_eodhd_snapshot(data,NOW,**kwargs)
    def check_wait(self,result):
        self.assertEqual(result["signal"],"WAIT")
        self.assertIs(result["executable"],False)
        self.assertIs(result["researchEligible"],False)
        self.assertEqual(result["engineStatus"],"NOT_INVOKED")
        self.assertEqual(result["sourceRequestsMade"],0)
        self.assertFalse(result["providerConnectionStarted"])

    def test_default_denies_snapshot_even_if_bid_ask_looks_valid(self):
        result=self.review(sample())
        self.check_wait(result)
        self.assertIn("SOURCE_RIGHTS_OR_PROVIDER_APPROVAL_MISSING",result["blockingReasons"])
        self.assertIn("INDEPENDENT_SESSION_HISTORY_OR_CLOCK_EVIDENCE_MISSING",result["blockingReasons"])
        self.assertIn("RESEARCH_EVALUATION_NOT_APPROVED",result["blockingReasons"])
        self.assertIn("INDICATOR_HISTORY_WARMUP_INSUFFICIENT",result["blockingReasons"])
        self.assertEqual(result["closedBarCounts"]["M15"],16)

    def test_partial_rights_or_fake_snapshot_flags_do_not_enable(self):
        s=sample()
        s["sessionVerified"]=True
        s["indicatorWarmupReady"]=True
        s["researchEligible"]=True
        self.check_wait(self.review(s))
        s["researchEligible"]=False
        self.check_wait(self.review(s,policy=SourcePolicy(True,True,True,True,"Reference","WRONG_PROVIDER")))

    def test_crossed_quotes_disagreement_and_unclosed_cannot_pass(self):
        for mutate in ("cross_open","cross_hilo","mid","row_time","ohlc","duplicate","h1_aggregate","h4_aggregate"):
            s=sample()
            if mutate=="cross_open":s["askFrames"]["M15"][-1]["open"]=3890
            elif mutate=="cross_hilo":s["askFrames"]["M15"][-1]["high"]=3890
            elif mutate=="mid":s["frames"]["M15"][-1]["close"]=1000
            elif mutate=="row_time":s["askFrames"]["M15"][-1]["openTime"]="2026-11-12T16:00:00Z"
            elif mutate=="ohlc":s["bidFrames"]["M15"][-1]["low"]=40000
            elif mutate=="h1_aggregate":s["bidFrames"]["H1"][-1]["high"]+=1
            elif mutate=="h4_aggregate":s["askFrames"]["H4"][-1]["high"]+=1
            else:s["bidFrames"]["M15"][-1]["openTime"]=s["bidFrames"]["M15"][-2]["openTime"]
            result=self.review(s)
            self.check_wait(result)
            self.assertTrue(any(v.startswith("BID_ASK_") for v in result["blockingReasons"]),mutate)

    def test_stale_quote_and_future_clock_are_blocking(self):
        for age in (31,-20):
            s=sample();s["latestQuote"]["timeUTC"]=(NOW-dt.timedelta(seconds=age)).isoformat()
            r=self.review(s)
            self.check_wait(r)
            self.assertIn("QUOTE_STALE_OR_FUTURE",r["blockingReasons"])

    def test_missing_session_and_incomplete_warmup_never_call_engines(self):
        evidence=IndependentEvidence(schedule_verified=True,schedule_reference="Test source",
                                     history_verified=True,history_reference="Test history",
                                     clock_verified=True,clock_reference="Test clock",
                                     expected_open_times={tf:[x["openTime"] for x in sample()["frames"][tf]]
                                                          for tf in ("M15","H1","H4")})
        p=SourcePolicy(True,True,True,True,"TEST ONLY","EODHD")
        r=self.review(sample(),evidence=evidence,policy=p,
                      context={"v3Feeds":{},"r2Feeds":{},"spread":0.4,"risk":{}},
                      allow_research_evaluation=True)
        self.check_wait(r)
        self.assertIn("INDICATOR_HISTORY_WARMUP_INSUFFICIENT",r["blockingReasons"])

    def test_mock_cannot_claim_live_research_without_50_h4_bars(self):
        s=sample(832)  # extra complete H4 groups for off-grid start/end
        self.assertGreaterEqual(len(s["bidFrames"]["H4"]),50)
        evidence=IndependentEvidence(
            schedule_verified=True,schedule_reference="UNIT TEST ONLY",
            history_verified=True,history_reference="UNIT TEST ONLY",
            clock_verified=True,clock_reference="UNIT TEST ONLY",
            expected_open_times={tf:[x["openTime"] for x in s["bidFrames"][tf]]
                                 for tf in ("M15","H1","H4")})
        p=SourcePolicy(True,True,True,True,"TEST ONLY","EODHD")
        mocked={"signal":"WAIT","executable":False,"researchEligible":True,
                "researchCandidate":"BUY","status":"RESEARCH_REVIEWED",
                "engines":{"v3":"REVIEWED"},"intake":{"blockingReasons":[]}}
        with patch("eodhd_research_bridge.run_research_pipeline", return_value=mocked) as evaluate:
            result=review_eodhd_snapshot(s,NOW,policy=p,evidence=evidence,
                     context={"v3Feeds":{},"r2Feeds":{},"spread":0.4,"risk":{}},
                     allow_research_evaluation=True)
        # The mocked return is about control-flow only, NOT real market analysis.
        self.assertEqual(result["signal"],"WAIT")
        self.assertFalse(result["executable"])
        self.assertEqual(result["dataConvention"],"INDICATIVE_EODHD_BID_OHLC_RESEARCH_ONLY")
        passed=evaluate.call_args.args[0]
        self.assertEqual(passed["frames"]["15min"]["candles"][-1]["close"],
                         s["bidFrames"]["M15"][-1]["close"])
        self.assertNotEqual(passed["frames"]["15min"]["candles"][-1]["close"],
                            s["frames"]["M15"][-1]["close"])

    def test_provider_calls_and_network_not_required(self):
        with patch("socket.socket",side_effect=AssertionError("network forbidden")):
            self.check_wait(self.review(sample()))

if __name__=="__main__":unittest.main()
