"""Self-contained, mobile-only BiQuote public data viewer safety regression.

The viewer does not use Capital.com credentials, Render, market order routes,
persistent archives, automatic paper orders or executable signals.
"""
import pathlib
import subprocess
import tempfile
import unittest

PATH=pathlib.Path(__file__).with_name("biquote_mobile_direct_research.html")
HTML=PATH.read_text(encoding="utf-8")

class MobileResearchTests(unittest.TestCase):
    def test_public_xauusd_only_and_no_execution_routes(self):
        self.assertIn("https://biquote.io",HTML)
        self.assertIn("/api/XAUUSD?allowStale=false",HTML)
        for interval in ("15m","1h","4h"):
            self.assertIn("interval="+interval,HTML)
        for bad in (
            "demo-api-capital.backend-capital.com",
            "api-capital.backend-capital.com",
            "/api/v1/positions",
            "/api/v1/session",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "POST",
            "WebSocket(",
            "executable:true",
            "paperOrdersAllowed:true",
        ):
            with self.subTest(forbidden=bad):
                self.assertNotIn(bad, HTML)
        self.assertIn("credentials:'omit'", HTML)
        self.assertIn("redirect:'error'", HTML)

    def test_explicit_stale_wait_and_closed_candle_guards(self):
        for expected in (
            "RESEARCH · WAIT", "جاهزية التداول", "WAIT",
            "q.marketState!=='open'", "q.stale===true",
            "now-time>30000", "q.ask<q.bid",
            "b.isOpen", "t+width<=now", "blankQuote()",
            "document.hidden", "setInterval(",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,HTML)
        self.assertIn("BiQuote",HTML)
        self.assertIn("ليس Capital.com",HTML)
        self.assertIn("لا تخزين سجل",HTML)

    def test_descriptive_observation_requires_contiguous_closed_bars(self):
        for expected in (
            "function ema20(", "function rsi14(", "function atr14(",
            "function technical(", "last-older!==width",
            "if(!b.isOpen&&t+width<=now)valid.push(b)",
            "technical(valid,tf)", "RESEARCH · WAIT",
            "لا إشارات تداول", "OPEN_NOT_FIRST",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,HTML)

    def test_inline_javascript_is_syntactically_valid(self):
        self.assertEqual(HTML.count("<script>"),1)
        self.assertEqual(HTML.count("</script>"),1)
        src=HTML.split("<script>",1)[1].split("</script>",1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/"viewer.js"
            p.write_text(src,encoding="utf-8")
            result=subprocess.run(["node","--check",str(p)],capture_output=True,
                                   text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":
    unittest.main()
