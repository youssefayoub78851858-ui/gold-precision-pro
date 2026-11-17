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

from biquote_public_one_shot import one_shot_probe
from xauusd_feed_gate import parse_utc

UTC = dt.timezone.utc
INTERVAL_SECONDS = 120
WINDOW_SECONDS = 86400
MAX_SAMPLES = WINDOW_SECONDS // INTERVAL_SECONDS
REQUESTS_PER_SAMPLE = 4
MAX_PUBLIC_REQUESTS = MAX_SAMPLES * REQUESTS_PER_SAMPLE
AUTHORIZATION_ENV = "GPP_BIQUOTE_PUBLIC_24H_REVIEW"
AUTHORIZATION_VALUE = "APPROVED_READONLY_NO_TRADING"

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
        self.archive_new_bars = {tf: 0 for tf in ("M15", "H1", "H4")}

    def add(self, result):
        self.samples += 1
        # Each probe attempts four fixed, public GETs and may fail individually.
        tried = result.get("requestCountAttempted")
        self.requests_attempted += tried if isinstance(tried, int) and 0 <= tried <= 4 else 0
        if not result.get("allHttp200AndValidJson"):
            self.http_failures += 1
            return
        self.http_ok += 1
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
            "privateArchiveNewClosedBars": dict(self.archive_new_bars),
            "orderEndpointsCalled": False,
            "cloudIndependentRightsProven": False,
            "marketSessionIndependentlyVerified": False,
            "providerSLAProven": False, "profitabilityTestPerformed": False,
            "warning": "Sparse public HTTP samples, not continuous uptime or broker-feed entitlement evidence"
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
                "archiveSavedSnapshotsSoFar": counters.archive_saved,
                "archiveRejectedSnapshotsSoFar": counters.archive_failed,
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
