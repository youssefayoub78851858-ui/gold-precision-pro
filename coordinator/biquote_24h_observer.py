"""BiQuote private review-only, bounded 24-hour quality observation worker.

Never emits trading signals beyond WAIT. Never collects a broker account,
API key, private quote history or PnL. This must be launched explicitly in
an isolated review environment; importing it starts NO connections/threads.
BiQuote's public HTTP responses are assessed at sparse 120-second snapshots;
these samples cannot prove sub-second availability or a 24/5 SLA.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time

from biquote_public_one_shot import one_shot_probe, DIAGNOSTIC_CODES
from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
INTERVAL_SECONDS = 120
WINDOW_SECONDS = 86400
MAX_SAMPLES = WINDOW_SECONDS // INTERVAL_SECONDS
REQUESTS_PER_SAMPLE = 4
MAX_PUBLIC_REQUESTS = MAX_SAMPLES * REQUESTS_PER_SAMPLE
AUTHORIZATION_ENV = "GPP_BIQUOTE_PUBLIC_24H_REVIEW"
AUTHORIZATION_VALUE = "APPROVED_READONLY_NO_TRADING"

# Private capture failures are deliberately bucketed into fixed, price-free
# labels. Raw error/provider text is never logged or forwarded to the demo.
PRIVATE_CAPTURE_CLASSES = (
    "NONE",
    "QUOTE_CLOCK_OR_MARKET",
    "QUOTE_PRICE_PARITY",
    "TICK_ORDER_OR_REVISION",
    "CLOSED_BAR_REVISION",
    "LATE_HISTORY_BACKFILL",
    "CLOSED_HISTORY_FRESHNESS",
    "CROSS_FRAME_PRICE_CONFLICT",
    "FRAME_STRUCTURE",
    "CAPACITY_LIMIT",
    "PRIVATE_STORAGE_SECURITY",
    "OTHER_PRIVATE_CAPTURE_FAILURE",
)

def classify_private_capture_failure(code):
    """Normalize a protected vault's rejection to a non-sensitive enum."""
    if type(code) is not str or not 3 <= len(code) <= 72:
        return "OTHER_PRIVATE_CAPTURE_FAILURE"
    if code in ("QUOTE_STALE_OR_FUTURE", "QUOTE_NOT_VALID_FRESH_OPEN",
                "OUT_OF_ORDER_TICK"):
        return ("TICK_ORDER_OR_REVISION" if code == "OUT_OF_ORDER_TICK"
                else "QUOTE_CLOCK_OR_MARKET")
    if code in ("MID_PARITY_FAILED", "QUOTE_SPREAD_PARITY_FAILED"):
        return "QUOTE_PRICE_PARITY"
    if code == "SAME_TICK_REVISED":
        return "TICK_ORDER_OR_REVISION"
    if code in ("CLOSED_CANDLE_REVISED_M15", "CLOSED_CANDLE_REVISED_H1",
                "CLOSED_CANDLE_REVISED_H4"):
        return "CLOSED_BAR_REVISION"
    if code in ("LATE_OR_OUT_OF_ORDER_BACKFILL_M15",
                "LATE_OR_OUT_OF_ORDER_BACKFILL_H1",
                "LATE_OR_OUT_OF_ORDER_BACKFILL_H4"):
        return "LATE_HISTORY_BACKFILL"
    if code in ("CLOSED_HISTORY_STALE_M15", "CLOSED_HISTORY_STALE_H1",
                "CLOSED_HISTORY_STALE_H4"):
        return "CLOSED_HISTORY_FRESHNESS"
    if code in ("CROSS_FRAME_OHLC_MISMATCH",
                "PARTIAL_CROSS_FRAME_OBSERVED_PRICE_BOUNDS_INVALID"):
        return "CROSS_FRAME_PRICE_CONFLICT"
    if code.startswith("FRAME_VALIDATION_"):
        return "FRAME_STRUCTURE"
    if code in ("QUOTE_OBSERVATION_CAP", "MAX_CANDLE_CAP_M15",
                "MAX_CANDLE_CAP_H1", "MAX_CANDLE_CAP_H4",
                "VAULT_STORAGE_BUDGET_REACHED", "VAULT_SIZE_EXCEEDED"):
        return "CAPACITY_LIMIT"
    if code in ("PRIVATE_ABSOLUTE_PATH_REQUIRED", "PRIVATE_DIR_REQUIRED",
                "VAULT_DIR_NOT_OWNER_ONLY", "VAULT_DIR_OWNER_MISMATCH",
                "VAULT_FILE_UNSAFE_PERMISSIONS_OR_SYMLINK",
                "VAULT_FILE_OWNER_MISMATCH", "VAULT_FILE_UNSAFE_AFTER_OPEN",
                "VAULT_TAMPER_OR_HASH_MISMATCH", "VAULT_UNREADABLE",
                "VAULT_PROVENANCE_INVALID"):
        return "PRIVATE_STORAGE_SECURITY"
    return "OTHER_PRIVATE_CAPTURE_FAILURE"

def _utc(value):
    if isinstance(value, dt.datetime) and value.tzinfo is not None and value.utcoffset() == dt.timedelta(0):
        return value.astimezone(UTC)
    if isinstance(value, str):
        return parse_utc(value)
    raise ValueError("EXPLICIT_UTC_REQUIRED")


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class QualityCounters:
    def __init__(self):
        self.samples = 0
        self.http_ok = 0
        self.audit_ok = 0
        self.market_open = 0
        self.quote_stale = 0
        self.http_failures = 0
        self.missing_ohlc_overlap = 0
        # All reported categories are fixed codes, never provider payloads.
        self.geometry_failure_classes = {
            key: 0 for key in (
                "UNCLASSIFIED_M15_COVERAGE_GAP",
                "OHLC_PRICE_DISAGREEMENT",
                "OTHER_SOURCE_SHAPE_FAILURE",
                "NO_STRUCTURAL_FAILURE",
                "UNAVAILABLE",
            )
        }
        self.evaluable_h1 = 0
        self.evaluable_h4 = 0
        self.disagree_h1 = 0
        self.disagree_h4 = 0
        self.gaps_h1 = 0
        self.gaps_h4 = 0
        self.age_max_seconds = None
        self.spread_min = None
        self.spread_max = None
        self.requests_attempted = 0
        self.archive_attempts = 0
        self.archive_saved = 0
        self.archive_failed = 0
        self.archive_failure_classes = {k: 0 for k in PRIVATE_CAPTURE_CLASSES if k != "NONE"}
        self.archive_new_bars = {tf: 0 for tf in ("M15", "H1", "H4")}
        # The previous 24-hour run had 29 failed snapshots but no per-endpoint
        # fault evidence. Future opt-in bounded observations distinguish them
        # using ONLY fixed integer counters (no raw feed or URL logging).
        self.endpoint_failure_codes = {
            tf: {code: 0 for code in DIAGNOSTIC_CODES if code != "OK"}
            for tf in ("quote","M15","H1","H4")}
        self.diagnostic_samples = 0
        self.independent_quote_age_over_30 = 0
        self.independent_quote_age_invalid = 0
        self.h4_retention_edges = 0
        self.h4_internal_m15_gaps_diagnostic = 0
        self.h4_partial_observed_price_conflicts = 0
        self.h4_missing_vendor_pause_reference = 0
        self.h4_missing_vendor_trading_reference = 0
        self.h4_missing_reference_unknown = 0

    def add(self, result):
        self.samples += 1
        # Each probe attempts four fixed, public GETs and may fail individually.
        tried = result.get("requestCountAttempted")
        self.requests_attempted += tried if isinstance(tried, int) and 0 <= tried <= 4 else 0
        diagnostic = result.get("qualityDiagnostic")
        if isinstance(diagnostic,dict) and (
            diagnostic.get("mode")=="BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY"
            and diagnostic.get("marketDataExposed") is False
            and diagnostic.get("sourceRequestsMade")==0
            and diagnostic.get("tradingEnabled") is False
            and isinstance(diagnostic.get("endpoint"),dict)
            and set(diagnostic["endpoint"])==set(self.endpoint_failure_codes)
            and all(code in DIAGNOSTIC_CODES
                    for code in diagnostic["endpoint"].values())):
            self.diagnostic_samples += 1
            for tf,code in diagnostic["endpoint"].items():
                if code!="OK":
                    self.endpoint_failure_codes[tf][code] += 1
            if diagnostic.get("independentQuoteAgeOver30Seconds") is True:
                self.independent_quote_age_over_30 += 1
            if diagnostic.get("independentQuoteAgeInvalid") is True:
                self.independent_quote_age_invalid += 1
            if result.get("allHttp200AndValidJson") is True:
                n=diagnostic.get("h4InternalM15Gaps")
                if type(n) is int and 0<=n<=10000:
                    self.h4_internal_m15_gaps_diagnostic+=n
                edges=diagnostic.get("h4RetentionEdgesIncomplete")
                if type(edges) is int and 0<=edges<=10000:
                    self.h4_retention_edges+=edges
                # Conservative subset-of-observed-M15 evidence. Repeats
                # across samples are summed as observations, NOT unique bars.
                for field,attr in (
                    ("h4PartialObservedPriceContradictions",
                     "h4_partial_observed_price_conflicts"),
                    ("h4MissingM15VendorPauseCandidates",
                     "h4_missing_vendor_pause_reference"),
                    ("h4MissingM15OutsideVendorReference",
                     "h4_missing_vendor_trading_reference"),
                    ("h4MissingM15ReferenceUnknown",
                     "h4_missing_reference_unknown")):
                    value=diagnostic.get(field)
                    if type(value) is int and 0<=value<=10000:
                        setattr(self,attr,getattr(self,attr)+value)
        if not result.get("allHttp200AndValidJson"):
            self.http_failures += 1
            return
        self.http_ok += 1
        kind = result.get("geometryFailureClass", "UNAVAILABLE")
        if kind not in self.geometry_failure_classes:
            kind = "UNAVAILABLE"
        self.geometry_failure_classes[kind] += 1
        private = result.get("privateArchive") or {}
        if private.get("attempted") is True:
            self.archive_attempts += 1
            if private.get("saved") is True:
                self.archive_saved += 1
                for tf in self.archive_new_bars:
                    n = private.get("newClosedBars", {}).get(tf, 0)
                    if type(n) is int and 0 <= n <= 1000:
                        self.archive_new_bars[tf] += n
            elif private.get("blockedReason"):
                self.archive_failed += 1
                category = classify_private_capture_failure(private.get("blockedReason"))
                self.archive_failure_classes[category] += 1
        if result.get("structuralAudit", {}).get("ohlcStructuralChecksPassed"):
            self.audit_ok += 1
        if result.get("dataGeometryConformance") == "SHAPE_CHECKS_FAILED_OR_INCOMPLETE":
            self.missing_ohlc_overlap += 1
        quote = next((item for item in result.get("httpResults", [])
                      if item.get("endpoint") == "quote"), {})
        if quote.get("marketState") == "open":
            self.market_open += 1
        if quote.get("providerStale") is True:
            self.quote_stale += 1
        if _numeric(quote.get("bid")) and _numeric(quote.get("ask")):
            spread = quote["ask"] - quote["bid"]
            if 0 <= spread < 100:
                self.spread_min = spread if self.spread_min is None else min(self.spread_min, spread)
                self.spread_max = spread if self.spread_max is None else max(self.spread_max, spread)
        age = result.get("structuralAudit", {}).get("quoteAgeSeconds")
        if _numeric(age):
            self.age_max_seconds = age if self.age_max_seconds is None else max(self.age_max_seconds, age)
        overlap = result.get("overlapEvidence", {}).get("overlap", {})
        for tf, suffix in (("H1","h1"),("H4","h4")):
            s = overlap.get(tf, {})
            setattr(self, "evaluable_"+suffix,
                    getattr(self, "evaluable_"+suffix) + int(s.get("fullyCoveredCompared", 0)))
            setattr(self, "disagree_"+suffix,
                    getattr(self, "disagree_"+suffix) + int(s.get("fullyCoveredOHLCDisagree", 0)))
            setattr(self, "gaps_"+suffix,
                    getattr(self, "gaps_"+suffix) + int(s.get("internalM15ConstituentGaps", 0)))

    def report(self, start_utc, as_of_utc, *, missed_slots, complete_window):
        return {
            "status": "RESEARCH_ONLY_24H_OBSERVATION",
            "signal": "WAIT", "executable": False,
            "researchEligible": False, "paperOrdersAllowed": False,
            "source": "BIQUOTE_PUBLIC_READONLY", "dataBasis": "MID_WITH_POSSIBLE_BID_SEED",
            "startedUTC": start_utc.isoformat().replace("+00:00", "Z"),
            "observedAsOfUTC": as_of_utc.isoformat().replace("+00:00", "Z"),
            "plannedHours": 24, "sampleIntervalSeconds": INTERVAL_SECONDS,
            "plannedSamples": MAX_SAMPLES, "samplesObserved": self.samples,
            "missedOrSkippedSlots": missed_slots, "completed24hWindow": complete_window,
            "requestsAttempted": self.requests_attempted,
            "maxPermittedRequests": MAX_PUBLIC_REQUESTS,
            "httpOkSamples": self.http_ok, "httpFailedSamples": self.http_failures,
            "auditShapePassedSamples": self.audit_ok, "marketOpenSamples": self.market_open,
            "providerStaleSamples": self.quote_stale,
            "crossFrameUnverifiedSamples": self.missing_ohlc_overlap,
            "geometryFailureClasses": dict(self.geometry_failure_classes),
            "diagnosticProtocol":"FIXED_ENDPOINT_FAILURE_COUNTS_NO_MARKET_DATA",
            "diagnosticSamples":self.diagnostic_samples,
            "endpointFailureCodes":self.endpoint_failure_codes,
            "independentQuoteOver30SecondsSamples":self.independent_quote_age_over_30,
            "independentQuoteAgeInvalidSamples":self.independent_quote_age_invalid,
            "h4RetentionEdgeIncompleteAcrossSnapshots":self.h4_retention_edges,
            "h4InternalM15GapsDiagnosedAcrossSnapshots":self.h4_internal_m15_gaps_diagnostic,
            "h4PartialObservedPriceConflictsAcrossSnapshots":self.h4_partial_observed_price_conflicts,
            "h4MissingM15VendorPauseReferenceAcrossSnapshots":self.h4_missing_vendor_pause_reference,
            "h4MissingM15VendorTradingReferenceAcrossSnapshots":self.h4_missing_vendor_trading_reference,
            "h4MissingM15ReferenceUnknownAcrossSnapshots":self.h4_missing_reference_unknown,
            "h1FullyCoveredComparedAcrossSnapshots": self.evaluable_h1,
            "h4FullyCoveredComparedAcrossSnapshots": self.evaluable_h4,
            "h1DisagreementsAcrossSnapshots": self.disagree_h1,
            "h4DisagreementsAcrossSnapshots": self.disagree_h4,
            "h1UnclassifiedPartialAggregatesAcrossSnapshots": self.gaps_h1,
            "h4UnclassifiedPartialAggregatesAcrossSnapshots": self.gaps_h4,
            "maxObservedQuoteAgeSeconds": self.age_max_seconds,
            "minObservedSpreadPrice": self.spread_min,
            "maxObservedSpreadPrice": self.spread_max,
            "rawQuotesPersisted": self.archive_saved > 0,
            "privateArchiveAttempts": self.archive_attempts,
            "privateArchiveSavedSnapshots": self.archive_saved,
            "privateArchiveRejectedSnapshots": self.archive_failed,
            "privateArchiveRejectedByClass": dict(self.archive_failure_classes),
            "privateArchiveNewClosedBars": dict(self.archive_new_bars),
            "orderEndpointsCalled": False,
            "cloudIndependentRightsProven": False,
            "marketSessionIndependentlyVerified": False,
            "providerSLAProven": False, "profitabilityTestPerformed": False,
            "warning": "Sparse public HTTP samples, not continuous uptime or broker-feed entitlement evidence"
        }



# Fixed-count-only source geometry evidence. Never exposes quotes, OHLC,
# timestamps, provider text, or a broker calendar verification claim.
_GEOMETRY_FIELDS = (
    "h1InternalM15Gaps", "h4InternalM15Gaps",
    "h4RetentionEdgesIncomplete", "h4MissingM15VendorPauseCandidates",
    "h4MissingM15OutsideVendorReference", "h4MissingM15ReferenceUnknown",
    "h4PartialObservedPriceContradictions",
    "h1CoveredOHLCDisagreements", "h4CoveredOHLCDisagreements",
)

def safe_sample_geometry_detail(result):
    """Sanitize public observation down to bounded integers; fail closed."""
    if not isinstance(result, dict) or result.get("allHttp200AndValidJson") is not True:
        return {"status": "UNAVAILABLE"}
    detail = result.get("qualityDiagnostic")
    if (not isinstance(detail, dict) or
            detail.get("mode") != "BIQUOTE_METADATA_FAILURE_DIAGNOSTICS_ONLY" or
            detail.get("marketDataExposed") is not False or
            detail.get("sourceRequestsMade") != 0 or
            detail.get("tradingEnabled") is not False or
            not isinstance(detail.get("endpoint"), dict) or
            set(detail["endpoint"]) != {"quote", "M15", "H1", "H4"} or
            any(detail["endpoint"][key] not in DIAGNOSTIC_CODES
                for key in ("quote", "M15", "H1", "H4"))):
        return {"status": "UNAVAILABLE"}
    counts = {}
    for field in _GEOMETRY_FIELDS:
        value = detail.get(field)
        if type(value) is not int or not 0 <= value <= 10000:
            return {"status": "UNAVAILABLE"}
        counts[field] = value
    return {
        "status": "COUNTS_ONLY_BROKER_CALENDAR_UNVERIFIED",
        "sourceQualified": False,
        "brokerSessionVerified": False,
        "frames": {
            "H1": {
                "internalMissingM15Groups": counts["h1InternalM15Gaps"],
                "fullyCoveredOHLCDisagreements": counts["h1CoveredOHLCDisagreements"],
            },
            "H4": {
                "internalMissingM15Groups": counts["h4InternalM15Gaps"],
                "retentionEdgeIncompleteGroups": counts["h4RetentionEdgesIncomplete"],
                "vendorReferencePauseMissingSlots": counts["h4MissingM15VendorPauseCandidates"],
                "outsideVendorReferenceMissingSlots": counts["h4MissingM15OutsideVendorReference"],
                "unknownReferenceMissingSlots": counts["h4MissingM15ReferenceUnknown"],
                "partialObservedOHLCContradictions": counts["h4PartialObservedPriceContradictions"],
                "fullyCoveredOHLCDisagreements": counts["h4CoveredOHLCDisagreements"],
            },
        },
    }


def observe_24h(start_utc, *, probe=one_shot_probe, utc_now=None,
                sleep=time.sleep, emit=None):
    """Bounded UTC-anchored 24h window: no makeup bursts or indefinite retries.

    On restart the SAME start_utc is required. Missed slots stay missed.
    Any real-network deployment must be manually authorized separately.
    """
    start = _utc(start_utc)
    now = (lambda: dt.datetime.now(UTC)) if utc_now is None else utc_now
    output = (lambda record: print(json.dumps(record, separators=(",", ":"), sort_keys=True),
                                   flush=True)) if emit is None else emit
    first = _utc(now())
    if start > first + dt.timedelta(minutes=15):
        # The ONLY permitted far-future start is the already fixed forward
        # holdout. It must be separately armed for private archival on the
        # reviewed Coordinator. The normal review CLI keeps the 15m guard.
        # The slot loop sleeps without fetching until its UTC start; no
        # second feed worker or early market-history collection is started.
        private_holdout_armed = (
            start == dt.datetime(2026, 11, 18, 0, 0, tzinfo=UTC)
            and os.environ.get("GPP_BIQUOTE_REVIEW_START_UTC")
                == "2026-11-18T00:00:00Z"
            and os.environ.get("GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE")
                == "APPROVED_READONLY_PRIVATE_NO_TRADING"
        )
        if not private_holdout_armed:
            raise ValueError("START_MORE_THAN_15_MINUTES_AHEAD")
    if first >= start + dt.timedelta(seconds=WINDOW_SECONDS):
        counters = QualityCounters()
        result = counters.report(start, first, missed_slots=MAX_SAMPLES,
                                 complete_window=False)
        result["windowExpiredBeforeWorkerStart"] = True
        output(result)
        return result
    counters = QualityCounters()
    missed = 0
    end = start + dt.timedelta(seconds=WINDOW_SECONDS)
    for slot in range(MAX_SAMPLES):
        slot_start = start + dt.timedelta(seconds=slot * INTERVAL_SECONDS)
        current = _utc(now())
        if current >= end:
            break
        if current < slot_start:
            sleep_seconds = min((slot_start-current).total_seconds(),
                                (end-current).total_seconds())
            if sleep_seconds > 0:
                sleep(sleep_seconds)
            current = _utc(now())
        if current >= end:
            break
        if current - slot_start >= dt.timedelta(seconds=INTERVAL_SECONDS):
            missed += 1
            continue
        try:
            result = probe()
        except Exception:
            # Never log raw provider error bodies or credentials.
            result = {"allHttp200AndValidJson": False, "requestCountAttempted": 0}
        counters.add(result)
        # No price, exact endpoint, or broker payload is persisted in the log.
        output({"event": "BIQUOTE_REVIEW24H_SAMPLE", "signal": "WAIT",
                "executable": False, "slot": slot,
                "asOfUTC": _utc(now()).isoformat().replace("+00:00", "Z"),
                "httpAllOk": result.get("allHttp200AndValidJson") is True,
                "geometryChecksOk": result.get("structuralAudit", {}).get("ohlcStructuralChecksPassed") is True,
                "geometryFailureClass": result.get("geometryFailureClass", "UNAVAILABLE"),
                "geometryDetail": safe_sample_geometry_detail(result),
                "archiveSavedSnapshotsSoFar": counters.archive_saved,
                "archiveRejectedSnapshotsSoFar": counters.archive_failed,
                "archiveRejectionClass": (classify_private_capture_failure(
                    result.get("privateArchive", {}).get("blockedReason"))
                    if result.get("privateArchive", {}).get("attempted") is True
                    and result.get("privateArchive", {}).get("blockedReason")
                    else "NONE"),
                "staleOrGapSamplesSoFar": counters.quote_stale + counters.missing_ohlc_overlap,
                "requestsAttemptedSoFar": counters.requests_attempted})
    # The final scheduled sample occurs at T+23h58m. Continue observing
    # the remaining 120 seconds before calling the 24-hour window complete.
    remaining = (end - _utc(now())).total_seconds()
    if remaining > 0:
        sleep(remaining)
    finished = _utc(now())
    complete_window = finished >= end and counters.samples + missed >= MAX_SAMPLES
    report = counters.report(start, finished, missed_slots=missed + max(
        0, MAX_SAMPLES - counters.samples - missed), complete_window=complete_window)
    output({"event": "BIQUOTE_REVIEW24H_REPORT", **report})
    return report


def main():
    parser = argparse.ArgumentParser(description="Explicitly gated 24-hour public BiQuote review observer")
    parser.add_argument("--start-utc", required=True, help="fixed UTC start; re-use across worker restarts")
    args = parser.parse_args()
    if os.environ.get(AUTHORIZATION_ENV) != AUTHORIZATION_VALUE:
        raise SystemExit("BLOCKED: set explicit read-only review authorization after workspace approval")
    start = _utc(args.start_utc)
    result = observe_24h(start)
    raise SystemExit(0 if result["completed24hWindow"] else 2)


if __name__ == "__main__":
    main()
