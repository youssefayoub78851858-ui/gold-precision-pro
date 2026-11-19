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

    def test_authenticated_monitor_uses_one_sealed_vault_snapshot(self):
        # Concurrent data capture may write a new vault while the mobile
        # status is evaluated. Three panels must share one sealed snapshot.
        self.assertIn("sealed=load_forward_vault(forward_vault_dir)",ENTRY)
        self.assertIn("inspect_forward_snapshot(sealed,now_utc=now)",ENTRY)
        self.assertIn("vault_metadata=metadata,sealed_vault=sealed",ENTRY)
        self.assertIn("now_utc=now",ENTRY)
        self.assertIn("vault_metadata=body['biquotePrivateForwardVault']",ENTRY)
        self.assertIn("shadow_status=body['biquoteForwardShadow']",ENTRY)
        self.assertNotIn("inspect_forward_metadata(forward_vault_dir)",ENTRY)
        self.assertNotIn("body['biquoteForwardShadow']=forward_shadow_review(forward_vault_dir)",ENTRY)
        self.assertNotIn("body['sealed']",ENTRY)
        self.assertNotIn("body['quoteObservations']",ENTRY)
        self.assertNotIn("body['closed']",ENTRY)
        self.assertIn("'signal':'WAIT'",ENTRY)
        self.assertIn("'paperOrdersAllowed':False",ENTRY)

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

    def test_private_quote_freshness_is_explicitly_wait_and_broker_unverified(self):
        for phrase in (
            'id="forward-freshness"',
            'vault.captureFreshness',
            'BIQUOTE_PRIVATE_CAPTURE_LIVENESS_DIAGNOSTIC_ONLY',
            'fresh?.sourceQualified===false',
            'fresh?.brokerCalendarVerified===false',
            'fresh?.captureVerifiedByBroker===false',
            'RECENT_UNVERIFIED',
            'STALE_OVER_5_MINUTES',
            'FUTURE_CAPTURE_OR_CLOCK_SKEW',
            'el("forward-freshness").textContent=freshnessText',
            'لم يُثبت وقت وصول آخر عينة BID/ASK',
            'غير معتمدة كمصدر تداول',
        ):
            self.assertIn(phrase,PUBLIC)
        self.assertNotIn("fresh.bid",PUBLIC)
        self.assertNotIn("fresh.ask",PUBLIC)
        self.assertNotIn("innerHTML",PUBLIC)
        self.assertNotIn("localStorage",PUBLIC)

    def test_stale_closed_candle_age_is_independent_from_bid_ask(self):
        # This is diagnostic-only: NEVER interpret 2-frame thresholds
        # as verified MT5 opening hours or live trade permission.
        for part in (
            'id="forward-candle-age"',
            'vault.closedFrameFreshness',
            'BIQUOTE_PRIVATE_CLOSED_FRAME_AGE_DIAGNOSTIC_ONLY',
            'bars?.sourceQualified===false',
            'bars?.brokerCalendarVerified===false',
            'bars?.gapBridgingAllowed===false',
            '["M15",1800],["H1",7200],["H4",28800]',
            'CANDLE_STALE_OVER_TWO_FRAMES',
            'FUTURE_CLOSE_OR_CLOCK_SKEW',
            'NO_CLOSED_BAR',
            'const bars=safeVault?vault.closedFrameFreshness:null',
            'el("forward-candle-age").textContent=candleAgeSafe',
            'لا يثبت ساعات الوسيط أو حقوق البيانات',
        ):
            self.assertIn(part,PUBLIC)
        self.assertNotIn('bars.bid',PUBLIC)
        self.assertNotIn('bars.ask',PUBLIC)
        self.assertNotIn('bars.prices',PUBLIC)
        self.assertNotIn('innerHTML',PUBLIC)

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
        # Safe metadata `vault.closedFrameFreshness` is allowed;
        # the raw closed-candle collection must stay inaccessible.
        for raw_collection in ('vault.closed[','vault.closed.','vault.closed?.',
                               'vault.closed;','vault.quoteObservations'):
            self.assertNotIn(raw_collection,PUBLIC)
        self.assertNotIn('vault.quoteObservations',PUBLIC)

    def test_archived_quote_mid_to_closed_ohlc_is_counts_only(self):
        for phrase in (
            'id="forward-mid-quote-parity"',
            'vault.quoteCandleMidGeometry',
            'PRIVATE_BIQUOTE_QUOTE_MID_CLOSED_OHLC_COUNTS_V1',
            'q?.brokerRightsVerified===false',
            'q?.independentBrokerPriceParityVerified===false',
            'OBSERVED_MID_OUTSIDE_CLOSED_OHLC',
            'CONSISTENT_OBSERVED_SAMPLES_ONLY',
            'el("forward-mid-quote-parity").textContent=',
            'لا يثبت مصدر الوسيط أو ترخيصه أو صلاحية التداول',
        ):
            self.assertIn(phrase,PUBLIC)
        for unsafe in (
            'q.bid','q.ask','q.open','q.high','q.low','q.close',
            'vault.quoteObservations','vault.closed[','innerHTML',
        ):
            self.assertNotIn(unsafe,PUBLIC)

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

    def test_unverified_broker_session_cannot_reclassify_raw_h4_warmup(self):
        for phrase in (
            'id="batch-session-warmup-state"',
            'const risk=complete?.sessionWarmupRisk',
            'STRICT_GRID_WARMUP_BROKER_CALENDAR_EVIDENCE_PENDING_V1',
            'risk?.brokerCalendarVerified===false',
            'risk?.sessionAwareWarmupAllowed===false',
            'risk?.missingCandleBridgingAllowed===false',
            'risk?.futureContinuityGuaranteed===false',
            'risk?.rawGridOnly===true',
            'risk.strictContiguous?.[tf]===batch.frameCounts?.[tf]?.contiguous',
            'risk.missingStrictClosedUntil21?.[tf]===missing?.[tf]',
            '&&riskSafe;',
            'قد تعيد عداد الشموع من الصفر',
        ):
            self.assertIn(phrase,PUBLIC)
        for phrase in ('risk.bid','risk.ask','risk.prices','innerHTML',
                       'CUTOVER_MODE=live'):
            self.assertNotIn(phrase,PUBLIC)

    def test_mobile_one_batch_completion_blockers_are_fail_closed(self):
        for phrase in (
            'id="batch-completion-state"',
            'id="batch-completion-blockers"',
            'batch.completionAudit',
            'GOLD_PRECISION_ONE_BATCH_COMPLETION_GATE_V1',
            'WAIT_EXTERNAL_EVIDENCE_AND_FORWARD_DATA',
            'complete?.paperOrdersAllowed===false',
            'complete?.liveOrdersAllowed===false',
            'complete?.archiveIntegrityObserved===',
            'complete.remainingBlockerCodes.every(code=>Object.hasOwn(blockerLabels,code))',
            'missing[tf]===Math.max(0,21-batch.frameCounts?.[tf]?.contiguous)',
            'BROKER_XAUUSD_SESSION_DST_UNCONFIRMED',
            'GC_TRADES_MBO_MBP10_LICENSING_NOT_ESTABLISHED',
            'OUT_OF_SAMPLE_NET_EXPECTANCY_NOT_PROVEN',
            'el("batch-completion-blockers").replaceChildren()',
            'todo.replaceChildren()',
        ):
            self.assertIn(phrase,PUBLIC)
        self.assertNotIn("innerHTML",PUBLIC)
        self.assertNotIn("localStorage",PUBLIC)
        self.assertNotIn("complete.bid",PUBLIC)
        self.assertNotIn("complete.ask",PUBLIC)
        self.assertNotIn("complete.entry",PUBLIC)

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
        self.assertIn('id="forward-readiness"', HTML)
        self.assertIn('vault.forwardCoverage?.H4?.latestContiguousBars', HTML)
        self.assertIn('Math.min(21,h4Run)', HTML)
        self.assertIn('Math.min(50,totals.H4)', HTML)
        self.assertIn('Math.min(50,totals.H1)', HTML)
        self.assertIn('Math.min(50,totals.M15)', HTML)
        self.assertIn('الأعداد وحدها لا تفعّل صفقات', HTML)
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
