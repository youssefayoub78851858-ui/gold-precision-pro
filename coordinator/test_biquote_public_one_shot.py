"""Unit-only simulation of one-shot BiQuote public REST check. NO networking."""
import datetime as dt
import io
import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

from biquote_public_one_shot import ENDPOINTS, one_shot_probe
from test_biquote_offline_source_audit import NOW, make_samples, iso


class FakeHTTPResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.payload[:size]


def fake_setup():
    quote, frames = make_samples()
    lookup = {"quote": quote, **frames}
    recorded = []

    def opener(request, timeout):
        recorded.append((request.full_url, request.get_method(),
                         request.has_header("Authorization"), timeout))
        name = dict((url, name) for name, url in ENDPOINTS)[request.full_url]
        return FakeHTTPResponse(lookup[name])

    return opener, recorded, lookup


class BiQuoteOneShotSafety(unittest.TestCase):
    def wait(self, output):
        self.assertEqual(output["status"], "WAIT_BIQUOTE_PUBLIC_ONE_SHOT")
        self.assertEqual(output["signal"], "WAIT")
        self.assertIs(output["executable"], False)
        self.assertIs(output["paperOrdersAllowed"], False)
        self.assertIs(output["researchEligible"], False)
        self.assertIs(output["providerConnected24x5"], False)
        self.assertIs(output["credentialsUsed"], False)
        self.assertIs(output["orderEndpointsCalled"], False)
        self.assertIs(output["marketDataStored"], False)
        self.assertIs(output["subscriptionActivated"], False)
        self.assertEqual(output["retryCount"], 0)
        self.assertEqual(output["requestCountAttempted"], 4)

    def test_successful_shape_still_wait_and_fixed_get_only(self):
        opener, calls, _ = fake_setup()
        with patch.object(socket, "socket", side_effect=AssertionError("NO_NETWORK")):
            report = one_shot_probe(opener, lambda: NOW)
        self.wait(report)
        self.assertTrue(report["allHttp200AndValidJson"])
        self.assertTrue(report["structuralAudit"]["ohlcStructuralChecksPassed"])
        self.assertEqual(report["structuralAudit"]["closedBarCounts"],
                         {"M15": 800, "H1": 200, "H4": 50})
        self.assertEqual([url for url, *_ in calls], [url for _, url in ENDPOINTS])
        self.assertTrue(all(method == "GET" and not auth and timeout == 12
                            for _, method, auth, timeout in calls))
        self.assertTrue(all("biquote.io/api/XAUUSD" in url for url, *_ in calls))
        self.assertFalse(report["structuralAudit"]["underlyingBrokerRightsWarranted"])
        self.assertIn("MID_", report["structuralAudit"]["candlePriceBasis"])

    def test_one_http_failure_never_retries_or_invents_three_frames(self):
        opener, calls, _ = fake_setup()
        def sometimes_failed(request, timeout):
            if "interval=4h" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 429,
                                             "rate limited", {}, None)
            return opener(request, timeout)

        r = one_shot_probe(sometimes_failed, lambda: NOW)
        self.wait(r)
        self.assertFalse(r["allHttp200AndValidJson"])
        self.assertNotIn("structuralAudit", r)
        self.assertEqual(r["httpResults"][3]["httpStatus"], 429)
        self.assertEqual(len(calls), 3)
        self.assertIn("PUBLIC_HTTP_NOT_FULLY_AVAILABLE", r["blockingReasons"])

    def test_future_quote_is_diagnostic_only_and_fails_audit(self):
        opener, _, lookup = fake_setup()
        lookup["quote"]["timestamp"] = iso(NOW + dt.timedelta(milliseconds=1))
        r = one_shot_probe(opener, lambda: NOW)
        self.wait(r)
        self.assertTrue(r["allHttp200AndValidJson"])
        self.assertIn("INDEPENDENT_QUOTE_CLOCK_FRESHNESS_FAILED",
                      r["structuralAudit"]["blockingReasons"])

    def test_unsupported_content_and_connection_failure_fail_closed(self):
        opener, _, _ = fake_setup()
        def corrupted(request, timeout):
            if "interval=1h" in request.full_url:
                return FakeHTTPResponse(["not", "a", "valid", "envelope"])
            return opener(request, timeout)

        r = one_shot_probe(corrupted, lambda: NOW)
        self.wait(r)
        self.assertFalse(r["allHttp200AndValidJson"])
        self.assertNotIn("structuralAudit", r)

        def offline(request, timeout):
            raise urllib.error.URLError("NO_NETWORK_TEST")
        r = one_shot_probe(offline, lambda: NOW)
        self.wait(r)
        self.assertFalse(r["allHttp200AndValidJson"])
        self.assertEqual(len(r["httpResults"]), 4)


if __name__ == "__main__":
    unittest.main()
