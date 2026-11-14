"""Offline FXCM bridge: native bar inspection never unlocks shared research."""
import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch

from fxcm_native_pipeline_bridge import review_fxcm_native_standby

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,16,0,tzinfo=UTC)
BASE=dt.datetime(2026,11,13,12,0,tzinfo=UTC)
def fixture():
    m15=[]
    for i in range(16):
        p={"open":4000+i*0.01,"high":4000+(i+1)*.01+.2,
           "low":3999+i*.01,"close":4000+(i+1)*.01}
        a={k:v+.3 for k,v in p.items()}
        m15.append({"openTime":(BASE+dt.timedelta(minutes=15*i)).isoformat().replace("+00:00","Z"),
                    "bid":p,"ask":a})
    def merge(n):
        result=[]
        for i in range(0,16,n):
            block=m15[i:i+n]
            item={"openTime":block[0]["openTime"]}
            for side in ("bid","ask"):
                item[side]={"open":block[0][side]["open"],
                    "high":max(x[side]["high"] for x in block),
                    "low":min(x[side]["low"] for x in block),
                    "close":block[-1][side]["close"]}
            result.append(item)
        return result
    return {"provider":"FXCM","source":"FOREXCONNECT_NATIVE_CPP",
            "instrument":"XAU/USD","receivedUTC":"2026-11-13T15:59:50Z",
            "frames":{"M15":m15,"H1":merge(4),"H4":merge(16)}}

class NativeBridgeTests(unittest.TestCase):
    def assert_safe(self, x):
        self.assertEqual(x["status"],"WAIT_FXCM_NATIVE_INTAKE_STANDBY")
        self.assertEqual(x["signal"],"WAIT")
        self.assertFalse(x["executable"])
        self.assertFalse(x["researchEligible"])
        self.assertEqual(x["researchCandidate"],"NONE")
        self.assertFalse(x["paperOrdersAllowed"])
        self.assertFalse(x["paperRunning"])
        self.assertFalse(x["sourcePolicyAuthorized"])
        self.assertFalse(x["rawCandlesIncluded"])
        self.assertEqual(x["providerRequestsMade"],0)
        self.assertEqual(x["credentialsRead"],0)
        self.assertFalse(x["sdkLoaded"])
        self.assertEqual(set(x["engines"].values()),{"SKIPPED"})
        self.assertNotIn('"bid":', json.dumps(x))
        self.assertNotIn('"ask":', json.dumps(x))
    def test_geometry_only_never_activates_research(self):
        x=review_fxcm_native_standby(fixture(),NOW)
        self.assert_safe(x)
        self.assertTrue(x["structuralAuditPassed"],x["blockingReasons"])
        self.assertEqual(x["checkedOverlaps"],{"H1":4,"H4":1})
        self.assertEqual(x["sharedResearchIntakeStatus"],"WAIT_INTAKE_BLOCKED")
    def test_forged_entitlement_and_order_fields_are_ignored(self):
        p=fixture()
        p.update(eulaSigned=True,sourceApproved=True,cloudUseAllowed=True,
                 sourcePolicyAuthorized=True,ordersAllowed=True,signal="BUY")
        x=review_fxcm_native_standby(p,NOW)
        self.assert_safe(x)
        self.assertTrue(x["structuralAuditPassed"])
    def test_crossed_market_never_arrives_at_engines(self):
        p=fixture()
        p["frames"]["M15"][0]["ask"]["open"]=0.01
        x=review_fxcm_native_standby(p,NOW)
        self.assert_safe(x)
        self.assertFalse(x["structuralAuditPassed"])
        self.assertIn("CROSSED_BID_ASK",x["blockingReasons"])
    def test_stale_data_is_blocked_before_engine(self):
        p=fixture()
        p["frames"]["M15"]=p["frames"]["M15"][:4]
        x=review_fxcm_native_standby(p,NOW)
        self.assert_safe(x)
        self.assertFalse(x["structuralAuditPassed"])
        self.assertIn("STALE_LATEST_CLOSED_CANDLE",x["blockingReasons"])
    def test_sdk_or_js_failure_is_wait(self):
        with patch("fxcm_native_pipeline_bridge.subprocess.run",
                   side_effect=OSError("Node unavailable")):
            x=review_fxcm_native_standby(fixture(),NOW)
        self.assert_safe(x)
        self.assertFalse(x["structuralAuditPassed"])
    def test_empty_payload_rejects(self):
        x=review_fxcm_native_standby(None,NOW)
        self.assert_safe(x)
        self.assertFalse(x["structuralAuditPassed"])

if __name__=="__main__":
    unittest.main()
