"""Offline fixed-limit capacity tests; synthetic metadata, no provider or disk."""
import json
import socket
import unittest
from unittest.mock import patch
from private_forward_capacity_preflight import capacity_readiness

def example(used=0,bars=None):
    return {"status":"PRIVATE_FORWARD_VAULT_METADATA_ONLY",
            "signal":"WAIT","executable":False,
            "paperOrdersAllowed":False,"tradeSignalReady":False,
            "quoteSamples":used,
            "counts":bars if bars is not None else {"M15":0,"H1":0,"H4":0}}

class CapacityReadinessTests(unittest.TestCase):
    def check_safe(self, x):
        self.assertEqual(x["mode"],"PRIVATE_FORWARD_CAPACITY_METADATA_ONLY")
        self.assertEqual(x["signal"],"WAIT")
        for k in ("executable","paperOrdersAllowed","liveOrdersAllowed",
                  "archiveActivationAllowed","autoDeleteOrRotateAllowed",
                  "sourceEntitlementVerified","marketDataExposed",
                  "projectionIsMarketDataOrUptimeForecast"):
            self.assertIs(x[k],False,k)
        self.assertEqual(x["providerRequestsMade"],0)
        for key in ("bid","ask","quoteObservations","privateToken",
                    "apiKey","rawCandles"):
            self.assertNotIn('"'+key+'"',json.dumps(x))
    def test_initial_has_headroom_but_not_activation(self):
        x=capacity_readiness(example())
        self.check_safe(x)
        self.assertEqual(x["status"],"CAPACITY_HEADROOM")
        self.assertEqual(x["quoteSamplesRemaining"],10000)
        self.assertEqual(x["closedBarsRemaining"],{"M15":45000,"H1":45000,"H4":45000})
        self.assertEqual(x["illustrativeRemainingHoursAtOneUniqueQuoteEvery2min"],333.3)
    def test_warning_at_80pct_then_stop_at_cap_without_deletion(self):
        warn=capacity_readiness(example(8000))
        self.check_safe(warn)
        self.assertEqual(warn["status"],"CAPACITY_WARNING")
        self.assertEqual(warn["quoteSamplesRemaining"],2000)
        full=capacity_readiness(example(10000))
        self.check_safe(full)
        self.assertEqual(full["status"],"CAPACITY_LIMIT_REACHED")
        self.assertEqual(full["quoteSamplesRemaining"],0)
        self.assertEqual(full["reasonCodes"],["CAPACITY_REQUIRES_OWNER_RETENTION_DECISION"])
        bar_warning=capacity_readiness(example(100,bars={"M15":36000,"H1":100,"H4":20}))
        self.assertEqual(bar_warning["status"],"CAPACITY_WARNING")
        full_bar=capacity_readiness(example(100,bars={"M15":45000,"H1":100,"H4":20}))
        self.assertEqual(full_bar["status"],"CAPACITY_LIMIT_REACHED")
    def test_reject_tampering_partial_counts_trading_promotion(self):
        for altered in (
            {"signal":"BUY"},{"executable":True},
            {"paperOrdersAllowed":True},{"tradeSignalReady":True},
            {"quoteSamples":-1},{"quoteSamples":10001},{"quoteSamples":True},
            {"quoteSamples":float("nan")},
            {"counts":{"M15":12,"H1":12,"H4":-1}},
            {"counts":{"M15":12,"H1":12}},
            {"counts":{"M15":45001,"H1":3,"H4":2}},
        ):
            with self.subTest(altered=altered):
                with self.assertRaises(ValueError):
                    capacity_readiness({**example(),**altered})
    def test_calculation_never_uses_network(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NETWORK_FORBIDDEN")):
            x=capacity_readiness(example(123))
        self.check_safe(x)
        self.assertEqual(x["quoteSamplesUsed"],123)

if __name__=="__main__":
    unittest.main()
