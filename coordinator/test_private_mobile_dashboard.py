"""Offline static contract for the private mobile monitor, no credentials/network."""
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parent
HTML=(ROOT/"private_mobile_dashboard.html").read_text(encoding="utf-8")
ENTRY=(ROOT/"entrypoint.py").read_text(encoding="utf-8")

class PrivateMobileDashboardTests(unittest.TestCase):
    def test_no_public_quote_or_trading_surface(self):
        self.assertIn("/api/v3/monitor/dashboard",ENTRY)
        self.assertIn("poll_private_review(",ENTRY)
        self.assertIn("monitor_ready=authenticated",ENTRY)
        self.assertIn("Cache-Control','no-store'",ENTRY)
        self.assertIn("Referrer-Policy','no-referrer'",ENTRY)
        self.assertIn("frame-ancestors 'none'",ENTRY)
        self.assertIn('type="password"',HTML)
        self.assertIn('autocomplete="off"',HTML)
        self.assertIn('location.protocol!=="https:"',HTML)
        self.assertIn('credentials:"omit"',HTML)
        self.assertIn('cache:"no-store"',HTML)
        self.assertIn("data.executable!==false",HTML)
        self.assertIn("data.researchEligible!==false",HTML)
        self.assertIn("data.engineStatus",HTML)
        self.assertIn("list.replaceChildren()",HTML)
        self.assertNotIn("localStorage",HTML)
        self.assertNotIn("sessionStorage",HTML)
        self.assertNotIn("innerHTML",HTML)
        self.assertNotIn("document.cookie",HTML)
        self.assertNotIn("OrderSend",HTML)
        self.assertNotIn("api_token=",HTML)
        self.assertNotIn("CUTOVER_MODE=live",HTML)

    def test_no_hidden_live_activation(self):
        self.assertIn("memoryToken",HTML)
        self.assertIn('el("auth").value=""',HTML)
        self.assertIn('el("clear").addEventListener',HTML)
        self.assertIn('engineStatus',HTML)
        self.assertIn('paperRunning',HTML)

if __name__=="__main__":unittest.main()
