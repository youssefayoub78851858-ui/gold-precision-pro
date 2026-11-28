import json
import unittest
import urllib.error
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
from massive_readonly_history_probe import probe_history,BASE

START="2026-11-04T00:00:00Z"
END="2026-11-04T00:15:00Z"
NOW="2026-11-04T01:00:00Z"
NS=1793750400000000000

class HistoryProbeTests(unittest.TestCase):
    def run_probe(self, rows, **extra):
        calls=[]
        def mock(req):
            calls.append(req)
            self.assertEqual(req.method,"GET")
            self.assertEqual(req.full_url.split("?")[0],BASE)
            self.assertEqual(req.get_header("Authorization"),"Bearer MOCK_ONLY")
            q=parse_qs(urlparse(req.full_url).query)
            self.assertEqual(q["timestamp.gte"],[str(NS)])
            self.assertEqual(q["timestamp.lt"],[str(NS+900*10**9)])
            self.assertNotIn("MOCK_ONLY",req.full_url)
            return json.dumps({"status":"OK","results":rows,**extra}).encode()
        report=probe_history(authorized=True,credential="MOCK_ONLY",
             start_utc=START,end_utc=END,now_utc=NOW,transport=mock)
        self.assertEqual(len(calls),1)
        self.assertFalse(report["historyCoverageVerified"])
        self.assertFalse(report["paperOrdersAllowed"])
        self.assertEqual(report["signal"],"WAIT")
        self.assertNotIn("MOCK_ONLY",repr(report))
        return report

    def test_default_never_connects(self):
        with patch("massive_readonly_history_probe._get",side_effect=AssertionError("no network")):
            self.assertEqual(probe_history()["providerRequestAttempts"],0)
            self.assertEqual(probe_history(authorized=True,credential="bad\nkey",
                start_utc=START,end_utc=END,now_utc=NOW)["status"],"INVALID_CONFIGURATION")

    def test_nanosecond_bbo_cursor_never_followed(self):
        row=dict(participant_timestamp=NS,bid_price=100,ask_price=100.4)
        result=self.run_probe([row,{**row,"participant_timestamp":NS+20*10**9+1}],
                              next_url="https://untrusted.invalid/not-followed")
        self.assertEqual(result["status"],"HISTORICAL_SAMPLE_OBSERVED_NOT_QUALIFIED")
        self.assertEqual(result["quoteCount"],2)
        self.assertTrue(result["truncated"])
        self.assertAlmostEqual(result["maxObservedGapSeconds"],20)
        self.assertNotIn("100.4",repr(result))

    def test_bad_quote_empty_and_out_of_window(self):
        row=dict(participant_timestamp=NS,bid_price=100,ask_price=100.4)
        self.assertEqual(self.run_probe([])["status"],"NO_QUOTES_OBSERVED")
        self.assertEqual(self.run_probe([{**row,"ask_price":99}])["status"],"HISTORICAL_SAMPLE_FAILED")
        self.assertEqual(self.run_probe([{**row,"participant_timestamp":NS-1}])["status"],"QUOTE_WINDOW_OR_ORDER_REJECTED")
        self.assertEqual(self.run_probe([{**row,"participant_timestamp":NS+1},row])["status"],"QUOTE_WINDOW_OR_ORDER_REJECTED")

    def test_http_denial_never_retries(self):
        def mock(req):
            raise urllib.error.HTTPError(req.full_url,403,"denied",{},None)
        r=probe_history(authorized=True,credential="MOCK_ONLY",start_utc=START,
            end_utc=END,now_utc=NOW,transport=mock)
        self.assertEqual(r["status"],"ENTITLEMENT_REFUSED")
        self.assertEqual(r["providerRequestAttempts"],1)

if __name__=="__main__":
    unittest.main()
