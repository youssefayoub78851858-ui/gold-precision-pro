"""The phone's FXCM card always reports offline-only standby evidence."""
import unittest
from unittest.mock import patch
from fxcm_mobile_readiness import read_fxcm_review_status, REASONS


class FXCMMobileReadinessTests(unittest.TestCase):
    def test_has_no_real_quote_or_permission_claim(self):
        r=read_fxcm_review_status()
        self.assertEqual(r["mode"], "OFFLINE_PREPARATION_ONLY")
        self.assertEqual(r["status"], "WAIT_FXCM_NOT_CONNECTED")
        self.assertEqual(r["signal"], "WAIT")
        for key in ("executable","researchEligible","paperOrdersAllowed",
                    "tradingEnabled","providerAccessStarted","sdkLoaded",
                    "livePricesAvailable","accountPermissionsVerified","licenseVerified"):
            self.assertIs(r[key], False)
        self.assertEqual(r["sourceRequestsMade"],0)
        self.assertEqual(r["credentialsRead"],0)
        self.assertEqual(r["validatedClosedBarCounts"],{"M15":0,"H1":0,"H4":0})
        self.assertEqual(r["blockingReasons"],list(REASONS))
        self.assertFalse({"bid","ask","price","apiKey","token","password"} & set(r))
    def test_independent_result_cannot_promote_future_reads(self):
        first=read_fxcm_review_status()
        first["blockingReasons"].clear()
        first["status"]="READY"
        first["validatedClosedBarCounts"]["M15"]=100
        fresh=read_fxcm_review_status()
        self.assertEqual(fresh["status"],"WAIT_FXCM_NOT_CONNECTED")
        self.assertEqual(fresh["validatedClosedBarCounts"]["M15"],0)
        self.assertEqual(fresh["blockingReasons"],list(REASONS))
    def test_no_network_or_sdk_loading(self):
        with patch("socket.socket",side_effect=AssertionError("network disallowed")):
            r=read_fxcm_review_status()
        self.assertEqual(r["sourceRequestsMade"],0)


if __name__=="__main__":
    unittest.main()
