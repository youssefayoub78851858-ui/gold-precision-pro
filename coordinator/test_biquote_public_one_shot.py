"""Unit-only simulation of one-shot BiQuote public REST check. NO networking."""
import datetime as dt
import io
import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

from biquote_public_one_shot import ENDPOINTS, one_shot_probe, public_log_summary
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
        self.assertEqual(report["dataGeometryConformance"],
                         "SHAPE_CHECKS_PASSED_BUT_UNLICENSED")
        self.assertEqual(report["overlapEvidence"]["overlap"]["H4"]
                         ["fullyCoveredAgree"], 50)
        self.assertFalse(report["overlapEvidence"]
                         ["sessionCalendarIndependentlyVerified"])
        self.assertEqual(report["structuralAudit"]["closedBarCounts"],
                         {"M15": 800, "H1": 200, "H4": 50})
        self.assertEqual([url for url, *_ in calls], [url for _, url in ENDPOINTS])
        self.assertTrue(all(method == "GET" and not auth and timeout == 12
                            for _, method, auth, timeout in calls))
        self.assertTrue(all("biquote.io/api/XAUUSD" in url for url, *_ in calls))
        self.assertFalse(report["structuralAudit"]["underlyingBrokerRightsWarranted"])
        self.assertEqual(report["sessionGapReferenceOnly"]["status"],
                         "REFERENCE_ONLY_NOT_BROKER_VERIFIED")
        self.assertIs(report["sessionGapReferenceOnly"]["brokerScheduleVerified"],False)
        self.assertIs(report["sessionGapReferenceOnly"]["executable"],False)
        self.assertEqual(report["sessionGapReferenceOnly"]["signal"],"WAIT")
        self.assertIn("MID_", report["structuralAudit"]["candlePriceBasis"])

    def test_public_ci_summary_never_logs_quote_prices_or_secrets(self):
        opener,_,packet=fake_setup()
        output=one_shot_probe(opener,lambda:NOW)
        self.assertTrue(output["allHttp200AndValidJson"])
        output["unknownSecret"]="MY_BROKER_API_KEY"
        output["httpResults"][0]["bid"]=123456789
        output["httpResults"][0]["ask"]=123456790
        output["qualityDiagnostic"]["providerApiKey"]="PRIVATE_VENDOR_KEY"
        safe=public_log_summary(output)
        self.assertEqual(safe["signal"],"WAIT")
        self.assertFalse(safe["executable"])
        self.assertFalse(safe["researchEligible"])
        self.assertFalse(safe["paperOrdersAllowed"])
        self.assertTrue(safe["allFourHttpAndJsonOk"])
        self.assertEqual(set(safe["fixedEndpointCodes"]),
                         {"quote","M15","H1","H4"})
        self.assertEqual(safe["fixedEndpointCodes"]["quote"],"OK")
        self.assertFalse(safe["brokerUpstreamRightsIndependentlyVerified"])
        self.assertFalse(safe["brokerSessionCalendarVerified"])
        self.assertFalse(safe["sourceAdmittedToTradeOrPaper"])
        serialized=json.dumps(safe)
        for sensitive in ("123456789","123456790","MY_BROKER_API_KEY",
                          "PRIVATE_VENDOR_KEY","apiKey",'"bid"','"ask"',
                          '"open"','"high"','"low"','"close"',"openTime","quoteObservations"):
            self.assertNotIn(sensitive,serialized)
        self.assertNotIn("httpResults",safe)
        self.assertNotIn("overlapEvidence",safe)
        self.assertNotIn("structuralAudit",safe)

    def test_public_ci_summary_rejects_vendor_injected_diagnostic_labels(self):
        packet={"qualityDiagnostic":{"endpoint":{
            "quote":"NEVER_PRINT_PROVIDER_AUTH_SECRET",
            "M15":"HTTP_429","H1":"INVALID_JSON_OR_ENVELOPE","H4":"OK"
        }},
        "allHttp200AndValidJson":False,
        "structuralAudit":{"quoteAgeSeconds":float("nan")}}
        safe=public_log_summary(packet)
        self.assertEqual(safe["fixedEndpointCodes"]["quote"],"NO_HTTP_RESPONSE")
        self.assertEqual(safe["fixedEndpointCodes"]["M15"],"HTTP_429")
        self.assertIsNone(safe["independentQuoteAgeSeconds"])
        self.assertFalse(safe["quoteAgeAcceptableAt30Seconds"])
        self.assertFalse(safe["allFourHttpAndJsonOk"])
        self.assertNotIn("NEVER_PRINT_PROVIDER_AUTH_SECRET",json.dumps(safe))

    def test_partial_internal_m15_gap_is_diagnosed_but_not_hidden(self):
        opener, _, packets = fake_setup()
        packets["M15"]["bars"].pop(150)
        result=one_shot_probe(opener,lambda:NOW)
        self.wait(result)
        self.assertTrue(result["allHttp200AndValidJson"])
        self.assertEqual(result["dataGeometryConformance"],
                         "SHAPE_CHECKS_FAILED_OR_INCOMPLETE")
        self.assertEqual(result["overlapEvidence"]["overlap"]["H1"]
                         ["internalM15ConstituentGaps"],1)
        self.assertIn("CROSS_TIMEFRAME_STRUCTURE_NOT_PROVEN",
                      result["blockingReasons"])

    def test_fixed_endpoint_fault_codes_do_not_expose_provider_payload(self):
        opener, calls, source = fake_setup()
        def mixed_response(request,timeout):
            if "interval=4h" in request.full_url:
                raise urllib.error.HTTPError(request.full_url,429,
                                             "SENSITIVE_GATEWAY_DETAIL",{},None)
            if "interval=1h" in request.full_url:
                return FakeHTTPResponse(["BAD_SECRET_ENVELOPE"])
            if "interval=15m" in request.full_url:
                raise urllib.error.URLError("PRIVATE_PASSWORD_DO_NOT_LOG")
            return opener(request,timeout)
        output=one_shot_probe(mixed_response, lambda:NOW)
        self.wait(output)
        diag=output["qualityDiagnostic"]
        self.assertEqual(diag["mode"],"BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY")
        self.assertEqual(diag["endpoint"],{
            "quote":"OK","M15":"NO_HTTP_RESPONSE",
            "H1":"INVALID_JSON_OR_ENVELOPE","H4":"HTTP_429"})
        self.assertFalse(diag["tradingEnabled"])
        self.assertEqual(diag["sourceRequestsMade"],0)
        self.assertFalse(diag["marketDataExposed"])
        encoded=json.dumps(diag)
        for secret in ("SENSITIVE_GATEWAY_DETAIL","PRIVATE_PASSWORD_DO_NOT_LOG",
                       "BAD_SECRET_ENVELOPE","https://","bid","ask","open","close"):
            self.assertNotIn(secret,encoded)
        self.assertEqual(len(calls),1)
        self.assertNotIn("structuralAudit",output)
        self.assertEqual(output["requestCountAttempted"],4)

    def test_quote_older_than_30_seconds_is_not_reinterpreted_as_fresh(self):
        opener, calls, data=fake_setup()
        data["quote"]["timestamp"]=iso(NOW-dt.timedelta(seconds=183))
        data["quote"]["stale"]=False
        out=one_shot_probe(opener,lambda:NOW)
        self.wait(out)
        self.assertTrue(out["allHttp200AndValidJson"])
        self.assertTrue(out["qualityDiagnostic"]["independentQuoteAgeOver30Seconds"])
        self.assertFalse(out["qualityDiagnostic"]["independentQuoteAgeInvalid"])
        self.assertIn("INDEPENDENT_QUOTE_CLOCK_FRESHNESS_FAILED",
                      out["structuralAudit"]["blockingReasons"])
        self.assertEqual(out["qualityDiagnostic"]["endpoint"],
                         {k:"OK" for k in ("quote","M15","H1","H4")})

    def test_invalid_future_quote_utc_does_not_pretend_to_be_valid(self):
        opener,_,data=fake_setup()
        data["quote"]["timestamp"]=iso(NOW+dt.timedelta(seconds=8))
        out=one_shot_probe(opener,lambda:NOW)
        self.assertTrue(out["qualityDiagnostic"]["independentQuoteAgeInvalid"])
        self.assertFalse(out["qualityDiagnostic"]["independentQuoteAgeOver30Seconds"])
        self.assertFalse(out["structuralAudit"]["ohlcStructuralChecksPassed"] is False and
                         "CROSS_TIMEFRAME_OHLC_MISMATCH" in
                         out["structuralAudit"]["blockingReasons"],
                         "A bad quote clock must not be recategorized as OHLC mismatch")

    def test_partial_h4_impossible_bound_still_counts_as_price_conflict(self):
        opener, calls, packets=fake_setup()
        packets["M15"]["bars"]=[
            row for row in packets["M15"]["bars"]
            if row["openTime"]!="2026-11-02T22:00:00Z"]
        h4=next(row for row in packets["H4"]["bars"]
                if row["openTime"]=="2026-11-02T20:00:00Z")
        h4["high"]=max(h4["open"],h4["close"])+0.01
        result=one_shot_probe(opener,lambda:NOW)
        self.wait(result)
        self.assertTrue(result["allHttp200AndValidJson"])
        self.assertFalse(result["structuralAudit"]["ohlcStructuralChecksPassed"])
        self.assertEqual(result["geometryFailureClass"],"OHLC_PRICE_DISAGREEMENT")
        q=result["qualityDiagnostic"]
        self.assertEqual(q["h4PartialObservedPriceContradictions"],1)
        self.assertEqual(q["h4MissingM15VendorPauseCandidates"],1)
        self.assertEqual(q["h4MissingM15OutsideVendorReference"],0)
        self.assertEqual(q["sourceRequestsMade"],0)
        self.assertFalse(q["marketDataExposed"])
        self.assertFalse(result["executable"])
        self.assertFalse(result["paperOrdersAllowed"])
        self.assertEqual(len(calls),4)

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
