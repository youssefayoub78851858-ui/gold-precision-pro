"""Zero-network egress contract tests; all tokens and broker prices fictional."""
import copy
import json
import socket
import unittest
from unittest.mock import patch

from capital_demo_egress_contract import (
    GATEWAY_POLICY, inspect_proposed_profile, inspect_intended_request
)

URL = ("https://demo-api-capital.backend-capital.com/api/v1/prices/"
       "TEST.GOLD.EPIC?resolution=MINUTE_15"
       "&from=2026-11-20T08%3A00%3A00"
       "&to=2026-11-20T11%3A45%3A01&max=1000")
HEADERS = ("CST", "X-SECURITY-TOKEN")


class EgressContractTests(unittest.TestCase):
    def never_trades(self, report):
        self.assertFalse(report["actualProxyInstalledAndEnforcing"])
        self.assertFalse(report["realNetworkIsolationVerified"])
        self.assertFalse(report["credentialsIsolatedOnHost"])
        self.assertFalse(report["providerTermsVerified"])
        self.assertFalse(report["sourceRightsApproved"])
        self.assertFalse(report["paperOrdersAllowed"])
        self.assertFalse(report["liveOrdersAllowed"])
        self.assertFalse(report["executable"])
        self.assertEqual(report["signal"], "WAIT")
        self.assertEqual(report["providerRequestsMade"], 0)
        self.assertEqual(report["brokerOrdersSent"], 0)
        text = json.dumps(report)
        for value in ("C" * 32, "T" * 32, "4000", "/var/data"):
            self.assertNotIn(value, text)

    def test_proposed_policy_does_not_attest_real_proxy(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            good = inspect_proposed_profile(copy.deepcopy(GATEWAY_POLICY))
        self.never_trades(good)
        self.assertEqual(good["status"], "SIMULATED_DESIGN_CONTRACT_MATCH_ONLY")
        self.assertTrue(good["proposedGatewayProfileMatchesRequirements"])
        self.assertFalse(good["realNetworkIsolationVerified"])
        for key, bad_value in [
            ("defaultDeny", False),
            ("allowedMethods", ["GET", "POST"]),
            ("upstreamScheme", "http"),
            ("forbidTradingHost", False),
            ("rejectRedirects", False),
            ("denyHttpConnectTunnels", False),
            ("denyWebsocketUpgrade", False),
            ("denyArbitraryForwardProxy", False),
            ("denyDirectEgressBypassingGateway", False),
            ("enforceHttpPathAfterTlsTermination", False),
            ("requireTokenHolderToBeSeparatePrivateProcess", False),
            ("denyTokenAccessFromPublicUiOrResearchWorkers", False),
            ("requireBrokerTlsCertificateHostnameValidation", False),
        ]:
            change = copy.deepcopy(GATEWAY_POLICY)
            change[key] = bad_value
            out = inspect_proposed_profile(change)
            self.never_trades(out)
            self.assertEqual(out["status"], "BLOCKED", key)
        self.never_trades(inspect_proposed_profile(None))
        proposed = dict(GATEWAY_POLICY, verifiedByOperator=True)
        self.never_trades(inspect_proposed_profile(proposed))
        self.assertEqual(inspect_proposed_profile(proposed)["status"], "BLOCKED")

    def test_get_only_research_shapes_with_inert_status(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            for resolution in ("MINUTE_15", "HOUR", "HOUR_4"):
                url = URL.replace("MINUTE_15", resolution)
                with self.subTest(resolution=resolution):
                    result = inspect_intended_request("GET", url, HEADERS,
                                                      effective_url=url)
                    self.never_trades(result)
                    self.assertEqual(result["status"], "SIMULATED_PRICE_GET_SHAPE_ONLY")
                    self.assertTrue(result["simulatedPriceGetShapeAllowed"])
                    self.assertFalse(result["actualProxyInstalledAndEnforcing"])

    def test_trading_routes_hosts_transports_and_redirects_denied(self):
        bad = [
            ("POST", URL, HEADERS, False, None),
            ("PUT", URL, HEADERS, False, None),
            ("DELETE", URL, HEADERS, False, None),
            ("PATCH", URL, HEADERS, False, None),
            ("CONNECT", URL, HEADERS, False, None),
            ("GET", URL.replace("/prices/", "/positions/"), HEADERS, False, None),
            ("GET", URL.replace("/prices/", "/workingorders/"), HEADERS, False, None),
            ("GET", URL.replace("/prices/", "/session/"), HEADERS, False, None),
            ("GET", URL.replace("/prices/", "/positions/otc/"), HEADERS, False, None),
            ("GET", URL.replace("demo-api-capital", "api-capital"), HEADERS, False, None),
            ("GET", URL.replace("https://", "http://"), HEADERS, False, None),
            ("GET", URL.replace(".com/api", ".com:8443/api"), HEADERS, False, None),
            ("GET", URL.replace("TEST.GOLD.EPIC", "..%2fpositions"), HEADERS, False, None),
            ("GET", URL.replace("TEST.GOLD.EPIC", "TEST.GOLD.EPIC/positions"), HEADERS, False, None),
            ("GET", URL + "#redirect", HEADERS, False, None),
            ("GET", URL + "&apiKey=secret", HEADERS, False, None),
            ("GET", URL.replace("max=1000", "max=10000"), HEADERS, False, None),
            ("GET", URL.replace("MINUTE_15", "MINUTE_1"), HEADERS, False, None),
            ("GET", URL, HEADERS, True, URL),
            ("GET", URL, HEADERS, False,
             "https://api-capital.backend-capital.com/api/v1/positions"),
            ("GET", URL, ("CST", "X-CAP-API-KEY"), False, None),
            ("GET", URL, ("CST", "X-SECURITY-TOKEN", "X-EXTRA"), False, None),
        ]
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            for method, url, headers, redirected, final in bad:
                with self.subTest(method=method, url=url[:100], final=final):
                    result = inspect_intended_request(
                        method, url, headers,
                        redirect_attempted=redirected, effective_url=final)
                    self.never_trades(result)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertFalse(result["simulatedPriceGetShapeAllowed"])

    def test_bad_types_and_unknown_profiles_fail_closed(self):
        for req in (
            (None, URL, HEADERS), ("GET", None, HEADERS),
            ("GET", URL, {"CST": "secret"}),
            ("GET", URL, ["CST", "CST"]),
            ("GET", URL, ["CST"]),
            ("GET", URL, None),
        ):
            result = inspect_intended_request(*req)
            self.never_trades(result)
            self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
