"""Offline static contract for the private mobile monitor, no credentials/network."""
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parent
HTML=(ROOT/"private_mobile_dashboard.html").read_text(encoding="utf-8")
ENTRY=(ROOT/"entrypoint.py").read_text(encoding="utf-8")
PUBLIC=(ROOT.parent/"private-monitor.html").read_text(encoding="utf-8")

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

    def test_public_android_viewer_uses_readonly_token_and_safe_archive(self):
        self.assertIn("MONITOR_READONLY_TOKEN", PUBLIC)
        self.assertIn('href="/ultimate#unified-mobile-trading"', PUBLIC)
        self.assertIn("افتح شاشة الذهب والشارت والتداول الورقي", PUBLIC)
        self.assertNotIn('رمز BROKER_TOKEN', PUBLIC)
        self.assertIn('id="biquote-shadow-review"', PUBLIC)
        self.assertIn('id="biquote-shadow-state"', PUBLIC)
        self.assertIn('id="biquote-shadow-coverage"', PUBLIC)
        self.assertIn('data.biquoteForwardShadow', PUBLIC)
        self.assertIn('shadow?.paperOrdersAllowed===false', PUBLIC)
        self.assertIn('shadow?.approvedDirection==="NONE"', PUBLIC)
        self.assertIn('id="biquote-forward-panel"', PUBLIC)
        for key in ("forward-m15", "forward-h1", "forward-h4",
                    "biquote-forward-state", "forward-last", "forward-coverage"):
            self.assertIn('id="' + key + '"', PUBLIC)
        self.assertIn("data.biquotePrivateForwardVault", PUBLIC)
        self.assertIn('vault?.tradeSignalReady===false', PUBLIC)
        self.assertIn('vault?.executable===false', PUBLIC)
        self.assertIn('vault?.paperOrdersAllowed===false', PUBLIC)
        self.assertIn('vault?.researchEligible===false', PUBLIC)
        self.assertIn('vault.forwardCoverage?.[tf]?.unclassifiedMissingSlots', PUBLIC)
        self.assertIn('el("forward-last").textContent=', PUBLIC)
        self.assertNotIn("innerHTML", PUBLIC)
        self.assertNotIn("localStorage", PUBLIC)
        self.assertNotIn("sessionStorage", PUBLIC)
        self.assertNotIn("OrderSend", PUBLIC)

    def test_biquote_forward_archive_counts_are_readonly_and_private(self):
        for tag in ('id="biquote-forward-panel"', 'id="forward-m15"',
                    'id="forward-h1"', 'id="forward-h4"',
                    'id="biquote-forward-state"', 'id="forward-last"',
                    'id="forward-coverage"'):
            self.assertIn(tag, HTML)
        self.assertIn('data.biquotePrivateForwardVault', HTML)
        self.assertIn('vault?.tradeSignalReady===false', HTML)
        self.assertIn('vault?.paperOrdersAllowed===false', HTML)
        self.assertIn('vault?.executable===false', HTML)
        self.assertIn('vault?.researchEligible===false', HTML)
        self.assertIn('vault?.status==="PRIVATE_FORWARD_VAULT_METADATA_ONLY"', HTML)
        self.assertIn('vault.forwardCoverage?.[tf]?.unclassifiedMissingSlots', HTML)
        self.assertIn('el("forward-last").textContent=', HTML)
        self.assertNotIn('vault.closed', HTML)
        self.assertNotIn('vault.quoteObservations', HTML)
        self.assertNotIn('innerHTML', HTML)

    def test_no_hidden_live_activation(self):
        self.assertIn("memoryToken",HTML)
        self.assertIn('id="fxcm-review-panel"',HTML)
        self.assertIn('id="fxcm-review-state"',HTML)
        self.assertIn('id="fxcm-review-reasons"',HTML)
        self.assertIn('data.fxcmReview',HTML)
        self.assertIn('fxcm?.livePricesAvailable===false',HTML)
        self.assertIn('fxcm?.licenseVerified===false',HTML)
        self.assertIn('fxcmReasons.replaceChildren()',HTML)
        self.assertIn('FXCM_EULA_AND_CLOUD_RIGHTS_UNVERIFIED',HTML)
        self.assertIn("read_fxcm_review_status()",ENTRY)
        self.assertIn('el("auth").value=""',HTML)
        self.assertIn('el("clear").addEventListener',HTML)
        self.assertIn('engineStatus',HTML)
        self.assertIn('paperRunning',HTML)

if __name__=="__main__":unittest.main()
