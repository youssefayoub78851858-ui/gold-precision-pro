"""One offline, synthetic preapproval integration battery for all four tracks."""
import os
import socket
import unittest
from unittest.mock import patch

from multi_source_readiness import assess_offline_stack
from paper_cost_preflight import synthetic_scenario_cost
from capital_demo_private_get_boundary import (
    inspect_private_demo_page, ENABLE_ENV, RIGHTS_ENV
)
from test_multi_source_readiness import xau, gc, AS_OF
from test_paper_cost_preflight import VALUES
from test_capital_demo_private_get_boundary import request


class PreapprovalFourTracksTests(unittest.TestCase):
    def test_offline_gc_trade_depth_dxy_and_bbo_never_become_market_data(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            v = assess_offline_stack(
                as_of_utc=AS_OF,
                xau_fixture=xau(),
                gc_mbo_fixture=gc("mbo"),
                gc_mbp10_fixture=gc("mbp-10")
            )
        self.assertEqual(v["signal"], "WAIT")
        self.assertFalse(v["executable"])
        self.assertFalse(v["paperOrdersAllowed"])
        self.assertEqual(v["verifiedLiveLayerCount"], 0)
        self.assertEqual(v["layers"]["DXY"]["status"], "NOT_CONNECTED")
        self.assertEqual(v["layers"]["GC_TRADES"]["status"], "SYNTHETIC_SCHEMA_ONLY")
        self.assertEqual(v["layers"]["GC_DEPTH"]["status"], "SYNTHETIC_SCHEMA_ONLY")
        for k in ("DXY","GC_TRADES","GC_DEPTH","XAUUSD_BBO"):
            self.assertFalse(v["layers"][k]["liveReady"])
            self.assertFalse(v["layers"][k]["researchAdmitted"])
        self.assertEqual(v["sourceRequestsMade"], 0)
        self.assertEqual(v["payments"], 0)

    def test_paper_cost_stress_rises_and_still_never_enables_orders(self):
        base = synthetic_scenario_cost(VALUES)
        stress = synthetic_scenario_cost({
            **VALUES, "spreadUsdPerOunce": 0.8,
            "entrySlippageUsdPerOunce": 0.3,
            "exitSlippageUsdPerOunce": 0.3,
        })
        for report in (base, stress):
            self.assertEqual(report["signal"], "WAIT")
            self.assertIs(report["executable"], False)
            self.assertIs(report["ordersAllowed"], False)
            self.assertIs(report["realBrokerEvidenceVerified"], False)
        self.assertGreater(stress["totalFrictionUsd"], base["totalFrictionUsd"])
        self.assertGreater(stress["targetGrossUsdToNet"], base["targetGrossUsdToNet"])
        self.assertGreater(stress["lossAtStopInclCostsUsd"], base["lossAtStopInclCostsUsd"])
        self.assertTrue(base["frictionConsumesFullRiskBudget"])

    def test_capital_demo_private_get_remains_disabled_even_with_fake_tokens(self):
        requests=[];deliveries=[]
        with patch.dict(os.environ, {ENABLE_ENV:"", RIGHTS_ENV:""}):
            with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
                v=inspect_private_demo_page(request(),cst="C"*32,
                   security_token="S"*32,explicit_operator_approval=True,
                   transport=lambda *args: requests.append(args),
                   deliver_private=deliveries.append)
        self.assertEqual(v["status"], "BLOCKED")
        self.assertEqual(v["signal"], "WAIT")
        self.assertFalse(v["executable"])
        self.assertFalse(v["researchEligible"])
        self.assertEqual(v["providerRequestsMade"], 0)
        self.assertEqual(v["brokerOrdersSent"], 0)
        self.assertEqual(requests,[])
        self.assertEqual(deliveries,[])


if __name__ == "__main__":
    unittest.main()
