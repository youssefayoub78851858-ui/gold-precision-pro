"""Isolated 0.01-lot stress and no-trade regression tests."""
import json
import math
import socket
import unittest
from unittest.mock import patch
from offline_broker_cost_stress import inspect_stress

BASE = {
    "dataOrigin": "SYNTHETIC_TEST_ONLY",
    "contractOuncesPerLot": 100,
    "lots": .01,
    "spreadUsdPerOunce": .4,
    "entrySlippageUsdPerOunce": .1,
    "exitSlippageUsdPerOunce": .1,
    "commissionRoundTripUsdPerLot": 7,
    "stopDistanceUsdPerOunce": 5,
    "targetNetUsd": 5,
    "equityUsd": 50,
    "riskFraction": .005,
    "dailyLossFraction": .02,
    "dailyLossUsedUsd": 0,
}


def variant(name, spread=1, entry=1, exit=1, commission=1):
    return dict(name=name, spreadMultiplier=spread,
                entrySlippageMultiplier=entry,
                exitSlippageMultiplier=exit, commissionMultiplier=commission)


def packet(baseline=None, scenarios=None):
    return dict(dataOrigin="SYNTHETIC_TEST_ONLY",
                baseline=BASE if baseline is None else baseline,
                scenarios=[variant("wide_spread", spread=3),
                           variant("slippage", entry=4, exit=4),
                           variant("fees", commission=4)]
                if scenarios is None else scenarios)


class CostStressTests(unittest.TestCase):
    def safe(self, out):
        self.assertEqual(out["mode"], "OFFLINE_SYNTHETIC_BROKER_FRICTION_STRESS_V1")
        self.assertEqual(out["signal"], "WAIT")
        self.assertEqual(out["ordersSent"], 0)
        self.assertEqual(out["brokerRequestsMade"], 0)
        for field in ("executable", "paperOrdersAllowed", "liveOrdersAllowed",
                      "brokerEvidenceVerified", "independentSpreadVerified",
                      "independentCommissionVerified", "forwardPerformanceValidated",
                      "tradingApproved"):
            self.assertIs(out[field], False, field)
        self.assertNotIn("SECRET", json.dumps(out))

    def test_small_equity_min_lot_and_adverse_costs_block(self):
        out = inspect_stress(packet())
        self.safe(out)
        self.assertEqual(out["status"], "BLOCKED_BY_SYNTHETIC_COST_STRESS")
        self.assertEqual(out["baselineFrictionUsd"], .67)
        self.assertEqual(out["baselineRiskBudgetUsd"], .25)
        self.assertEqual(out["scenariosChecked"], 4)
        self.assertFalse(out["stressRiskWithinBudget"])
        self.assertEqual(out["worstScenario"], "simultaneous_worst")
        self.assertAlmostEqual(out["worstModeledStopLossPlusCostsUsd"], 7.28)
        self.assertTrue(all(not x["hypotheticalRiskWithinBudget"]
                            for x in out["results"]))

    def test_larger_equity_within_budget_is_still_not_authorized(self):
        out = inspect_stress(packet(baseline={**BASE, "equityUsd": 5000}))
        self.safe(out)
        self.assertEqual(out["status"], "UNATTESTED_SYNTHETIC_RISK_WITHIN_BUDGET")
        self.assertTrue(out["stressRiskWithinBudget"])
        self.assertFalse(out["tradingApproved"])

    def test_malformed_unauthorized_and_nonadverse_never_arms(self):
        invalid = [
            None, {}, {"dataOrigin": "LIVE", "baseline": BASE, "scenarios": []},
            {**packet(), "tradeApproved": True},
            packet(baseline={**BASE, "dataOrigin": "BROKER"}),
            packet(baseline={**BASE, "apiKey": "SECRET"}),
            packet(baseline={**BASE, "lots": float("nan")}),
            packet(scenarios=[]),
            packet(scenarios=[variant("flat")]),
            packet(scenarios=[variant("dupe", spread=2), variant("dupe", spread=3)]),
            packet(scenarios=[variant("bad-name", spread=2)]),
            packet(scenarios=[variant("bad", spread=0)]),
            packet(scenarios=[variant("bad", commission=math.inf)]),
            packet(scenarios=[{**variant("extra", spread=2), "license": True}]),
            packet(scenarios=[variant("x", spread=2)]*9),
        ]
        for case in invalid:
            with self.subTest(case=str(case)[:120]):
                out = inspect_stress(case)
                self.safe(out)
                self.assertEqual(out["status"], "BLOCKED")

    def test_multiplier_on_zero_fee_is_not_adverse_stress(self):
        zeros = {**BASE, "spreadUsdPerOunce": 0,
                 "entrySlippageUsdPerOunce": 0,
                 "exitSlippageUsdPerOunce": 0,
                 "commissionRoundTripUsdPerLot": 0}
        out = inspect_stress(packet(baseline=zeros))
        self.safe(out)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason"], "NO_EFFECTIVE_COST_STRESS")

    def test_no_network_and_no_private_prices(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            out = inspect_stress(packet())
        self.safe(out)
        raw = json.dumps(out)
        for secret in ("ask_price", "bid_price", "apiKey", "privateToken"):
            self.assertNotIn(secret, raw)


if __name__ == "__main__":
    unittest.main()
