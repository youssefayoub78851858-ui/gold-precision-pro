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
        self.assertIn("21 شمعة H4", PUBLIC)
        self.assertIn("84 ساعة نظرياً", PUBLIC)
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

    def test_vendor_gap_reference_mobile_never_claims_broker_schedule(self):
        self.assertIn('id="forward-gap-reference"',PUBLIC)
        self.assertIn('vault.gapReference',PUBLIC)
        self.assertIn('referenceSafe',PUBLIC)
        self.assertIn('ref?.independentBrokerCalendarVerified===false',PUBLIC)
        self.assertIn('ref?.sourceRightsVerified===false',PUBLIC)
        self.assertIn('ref?.allGapsRemainUnclassified===true',PUBLIC)
        self.assertIn('ref?.paperOrdersAllowed===false',PUBLIC)
        self.assertIn('el("forward-gap-reference").textContent=',PUBLIC)
        self.assertIn("لا تثبت اكتمال بيانات BiQuote أو صلاحية التداول",PUBLIC)
        self.assertNotIn('vault.closed',PUBLIC)
        self.assertNotIn('vault.quoteObservations',PUBLIC)

    def test_mobile_shadow_parity_uses_only_safe_comparison_counts(self):
        self.assertIn('id="biquote-parity-state"',PUBLIC)
        self.assertIn("shadow.diagnosticCrossFrameParity",PUBLIC)
        self.assertIn('proof?.sourceRightsVerified===false',PUBLIC)
        self.assertIn('proof?.brokerCalendarVerified===false',PUBLIC)
        self.assertIn('proof?.paperOrdersAllowed===false',PUBLIC)
        self.assertIn('row.fullyCoveredCompared+row.notFullyCovered',PUBLIC)
        self.assertIn('row.fullyCoveredDisagreed>row.fullyCoveredCompared',PUBLIC)
        self.assertIn('el("biquote-parity-state").textContent=',PUBLIC)
        self.assertIn("لا يثبت ترخيص المصدر أو صلاحية التداول",PUBLIC)
        self.assertNotIn("shadow.privateOHLC",PUBLIC)
        self.assertNotIn("innerHTML",PUBLIC)

    def test_v3_mobile_shows_saved_vs_strict_and_vendor_pause_unverified(self):
        for phrase in (
            'id="biquote-warmup-gap"',
            'shadow.warmupContinuity',
            'STRICT_RAW_CLOSED_BARS_BROKER_CALENDAR_UNVERIFIED',
            'warmup?.brokerCalendarVerified===false',
            'warmup?.sourceRightsVerified===false',
            'warmup?.gapBridgingAllowed===false',
            'g.strictLatestContiguous!==f.contiguousClosed',
            'g.remainingUntil21!==Math.max(0,21-f.contiguousClosed)',
            'g.vendorPauseCandidatesNotVerified+g.outsideVendorReferenceSlots',
            'const watchSafe=safeShadow&&paritySafe&&warmupOk',
            'ولا يُعتمد أي جدول جلسات قبل توثيقه من الوسيط'
        ):
            self.assertIn(phrase,PUBLIC)
        self.assertIn('el("biquote-warmup-gap").textContent=',PUBLIC)
        self.assertNotIn('shadow.closed',PUBLIC)
        self.assertNotIn('shadow.privateOHLC',PUBLIC)
        self.assertNotIn('innerHTML',PUBLIC)

    def test_v3_mobile_watch_needs_full_closed_warmup_and_overlap(self):
        # A BUY/SELL technical *watch* is not a trade, yet it still must
        # never appear based only on a claimed frozen-engine result.
        for phrase in (
            'const watchSafe=safeShadow&&paritySafe',
            'shadow.engineReview==="FROZEN_V3_COMPLETED_WITH_REAL_OBSERVED_CLOSED_BARS"',
            '["M15","H1","H4"].every(tf=>',
            'f.contiguousClosed>=21',
            'p.fullyCoveredCompared>=1&&p.fullyCoveredDisagreed===0',
            'const side=watchSafe?shadow.technicalWatch:"NONE"'
        ):
            self.assertIn(phrase,PUBLIC)
        self.assertNotIn('const side=safeShadow?shadow.technicalWatch',PUBLIC)
        self.assertIn('لم تكتمل الأدلة والشموع',PUBLIC)
        self.assertNotIn('innerHTML',PUBLIC)
        self.assertNotIn('localStorage',PUBLIC)

    def test_private_four_stage_batch_has_locked_mobile_evidence(self):
        for tag in ('id="four-stage-private-panel"', 'id="batch-readiness-state"',
                    'id="batch-data-state"', 'id="batch-archive-state"',
                    'id="batch-analysis-state"', 'id="batch-paper-state"',
                    'id="batch-frames-state"'):
            self.assertIn(tag,PUBLIC)
        self.assertIn('id="batch-capacity-state"',PUBLIC)
        self.assertIn("batch.quoteSamplesRemaining",PUBLIC)
        self.assertIn("CAPACITY_LIMIT_REACHED",PUBLIC)
        self.assertIn("CAPACITY_METADATA_UNAVAILABLE",PUBLIC)
        self.assertIn("data.ultimateFourStageBatch",PUBLIC)
        self.assertIn('batch?.paperOrdersAllowed===false',PUBLIC)
        self.assertIn('batch?.liveOrdersAllowed===false',PUBLIC)
        self.assertIn('batch?.independentlyQualified===false',PUBLIC)
        self.assertIn('el("batch-paper-state").textContent="BLOCKED"',PUBLIC)
        self.assertIn("clearBatchDisplay()",PUBLIC)
        self.assertNotIn('batch.entry',PUBLIC)
        self.assertNotIn('batch.stopLoss',PUBLIC)
        self.assertNotIn('batch.takeProfit',PUBLIC)
        self.assertIn("four_stage_batch_review(",ENTRY)
        self.assertIn("shadow_status=body['biquoteForwardShadow']",ENTRY)

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
