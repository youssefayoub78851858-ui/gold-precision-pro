"""Broker cost model: explicit synthetic assumptions, never real prices or orders."""
import math
import json
import socket
import unittest
from unittest.mock import patch
from paper_cost_preflight import cost_readiness, synthetic_scenario_cost

VALUES = {
    "dataOrigin": "SYNTHETIC_TEST_ONLY",
    "contractOuncesPerLot": 100, "lots": 0.01,
    "spreadUsdPerOunce": 0.4,
    "entrySlippageUsdPerOunce": 0.1,
    "exitSlippageUsdPerOunce": 0.1,
    "commissionRoundTripUsdPerLot": 7.0,
    "stopDistanceUsdPerOunce": 5.0,
    "targetNetUsd": 5.0,
    "equityUsd": 50.0,
    "riskFraction": 0.005,
    "dailyLossFraction": 0.02,
    "dailyLossUsedUsd": 0.0,
}

class CostTests(unittest.TestCase):
    def test_missing_and_unverified_real_evidence(self):
        result = cost_readiness()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["signal"], "WAIT")
        self.assertIs(result["executable"], False)
        self.assertFalse(result["ordersAllowed"])
        self.assertFalse(result["realBrokerFeesVerified"])
        self.assertEqual(len(result["reasonCodes"]), 4)
        self.assertNotIn("spreadRoundTripUsd", result)

    def test_cost_arithmetic_and_risk_ceiling_is_synthetic(self):
        x = synthetic_scenario_cost(VALUES)
        self.assertAlmostEqual(x["spreadRoundTripUsd"], .4)
        self.assertAlmostEqual(x["slippageRoundTripUsd"], .2)
        self.assertAlmostEqual(x["commissionRoundTripUsd"], .07)
        self.assertAlmostEqual(x["totalFrictionUsd"], .67)
        self.assertAlmostEqual(x["targetGrossUsdToNet"], 5.67)
        self.assertAlmostEqual(x["priceMoveUsdPerOunceToNetTarget"], 5.67)
        self.assertAlmostEqual(x["lossAtStopInclCostsUsd"], 5.67)
        self.assertAlmostEqual(x["riskBudgetUsd"], .25)
        self.assertFalse(x["hypotheticalRiskWithinBudget"])
        self.assertEqual(x["status"], "BLOCKED")
        self.assertEqual(x["signal"], "WAIT")
        self.assertIs(x["executable"], False)
        self.assertFalse(x["ordersAllowed"])
        self.assertEqual(x["dataOrigin"], "SYNTHETIC_TEST_ONLY")
        self.assertFalse(x["realBrokerEvidenceVerified"])

    def test_cost_is_spread_once_even_for_sell(self):
        x = synthetic_scenario_cost({**VALUES, "equityUsd": 5000.0})
        self.assertAlmostEqual(x["spreadRoundTripUsd"], .4)
        self.assertTrue(x["hypotheticalRiskWithinBudget"])
        self.assertFalse(x["ordersAllowed"])

    def test_missing_broker_fields_price_or_invalid_values_block(self):
        for name in (
            "contractOuncesPerLot", "lots", "spreadUsdPerOunce",
            "entrySlippageUsdPerOunce", "exitSlippageUsdPerOunce",
            "commissionRoundTripUsdPerLot", "equityUsd", "targetNetUsd",
        ):
            p = dict(VALUES);p.pop(name)
            with self.assertRaises(ValueError):
                synthetic_scenario_cost(p)
        for name, invalid in (
            ("lots", -1), ("spreadUsdPerOunce", -0.2),
            ("entrySlippageUsdPerOunce", math.nan),
            ("commissionRoundTripUsdPerLot", math.inf),
            ("riskFraction", 0.1), ("dailyLossFraction", 0.03),
            ("contractOuncesPerLot", 0), ("lots", True),
        ):
            with self.subTest(name=name, invalid=str(invalid)):
                with self.assertRaises(ValueError):
                    synthetic_scenario_cost({**VALUES, name: invalid})
        for bad_origin in ("EODHD", "BROKER", "RECORDED", "LIVE", None):
            with self.assertRaises(ValueError):
                synthetic_scenario_cost({**VALUES,"dataOrigin":bad_origin})
        with self.assertRaises(ValueError):
            synthetic_scenario_cost({**VALUES,"apiKey":"not acceptable"})

    def test_calculation_has_no_network_or_account(self):
        with patch.object(socket,"socket",side_effect=AssertionError("Network forbidden")):
            x=synthetic_scenario_cost(VALUES)
            y=cost_readiness()
        self.assertEqual(y["status"],"BLOCKED")
        self.assertNotIn("apiKey",json.dumps(x))
        self.assertFalse(x["paperTradingApproved"])

if __name__=="__main__":
    unittest.main()
