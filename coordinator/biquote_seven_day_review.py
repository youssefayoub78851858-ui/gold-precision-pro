"""Seven-day bounded private BiQuote research capture, opt-in and WAIT only.

This extends the existing 24h observer, NOT the live trading engine. It reuses
the SAME 4 public GETs in each 120-second slot and the owner-only sealed vault.
Never launches by import. Never assumes rights to the underlying MT5 broker.
It cannot auto-rotate/delete data, fill missed market bars or submit orders.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import time

from biquote_24h_observer import (
    observe_24h, AUTHORIZATION_ENV, AUTHORIZATION_VALUE,
    MAX_SAMPLES, WINDOW_SECONDS,
)
from biquote_public_one_shot import one_shot_probe
from biquote_private_forward_vault import (
    START, APPROVAL_ENV, APPROVAL, ingest, inspect_metadata, load_vault,
)
from biquote_session_gap_audit import audit_closed_timestamp_reference
from biquote_forward_shadow_review import tail_contiguous, overlaps_match, WIDTH
from private_forward_capacity_preflight import capacity_readiness
from biquote_quote_mid_parity import audit_closed_quote_mid_parity
from biquote_sampled_spread_buckets import audited_sampled_spread_buckets, BINS
from biquote_quote_cadence import audit_quote_cadence, INTERVAL_BINS, LAG_BINS

UTC = dt.timezone.utc
DAYS = 7
SEVEN_DAY_ENV = "GPP_BIQUOTE_7DAY_FORWARD_REVIEW"
SEVEN_DAY_VALUE = "APPROVED_SEVEN_DAYS_READONLY_NO_TRADING"
# A second seven-day review must not inherit the first window's consent.
RENEWAL_ENV = "GPP_BIQUOTE_NEXT_7DAY_APPROVAL"
RENEWAL_VALUE = "APPROVED_SEPARATE_7DAY_RESEARCH_NO_TRADING"
RENEWAL_START_ENV = "GPP_BIQUOTE_NEXT_7DAY_START_UTC"
SAFE = {"signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
        "liveOrdersAllowed": False, "tradeEligible": False, "researchEligible": False,
        "brokerOrdersSent": 0, "paperOrdersCreated": 0}


def approved(environment=None):
    values = os.environ if environment is None else environment
    return (values.get("CUTOVER_MODE", "standby") == "standby"
            and values.get(AUTHORIZATION_ENV) == AUTHORIZATION_VALUE
            and values.get(APPROVAL_ENV) == APPROVAL
            and values.get(SEVEN_DAY_ENV) == SEVEN_DAY_VALUE)


def _utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC_AWARE_CLOCK_REQUIRED")
    return value.astimezone(UTC)


def run_seven_days(vault_dir, *, anchor=START, clock=None, sleep=None,
                   observer=observe_24h, source_probe=one_shot_probe,
                   archive=ingest, metadata=inspect_metadata,
                   emit=None, environment=None, days=DAYS):
    """One bounded worker; no second polling loop and no catch-up bursts.

    Missing past slots are *skipped*, never backfilled; expired days aren't
    rerun. A daily budget reserves 720 quote slots before touching the source.
    Existing archive hashes/revisions/permissions stay enforced by ingest.
    Injectable clock/transport exists for zero-network unit tests only.
    """
    if not approved(environment):
        raise ValueError("SEPARATE_SEVEN_DAY_PRIVATE_APPROVAL_REQUIRED")
    folder = pathlib.Path(vault_dir)
    if (not folder.is_absolute() or not str(folder).startswith("/var/data/")
            or ".." in folder.parts):
        raise ValueError("OWNER_ONLY_PERSISTENT_DISK_REQUIRED")
    if type(days) is not int or not 1 <= days <= DAYS:
        raise ValueError("HOLDOUT_ANCHOR_OR_WINDOW_INVALID")
    anchor = _utc(anchor)
    if anchor != START:
        extra = os.environ if environment is None else environment
        # Only the next exact week may ever use this distinct approval.
        # No automatic renewal or roll-forward to a third interval.
        if (anchor != START + dt.timedelta(days=DAYS) or
            extra.get(RENEWAL_ENV) != RENEWAL_VALUE or
            extra.get(RENEWAL_START_ENV) !=
                anchor.strftime("%Y-%m-%dT%H:%M:%SZ")):
            raise ValueError("EXPLICIT_NEXT_SEVEN_DAY_APPROVAL_REQUIRED")
    get_time = clock or (lambda: dt.datetime.now(UTC))
    do_sleep = sleep or time.sleep
    # Default logs contain fixed metadata only. Private quote prices, source
    # JSON and full vault paths never enter Render application logs.
    def safe_log(record):
        print("BIQUOTE_SEVEN_DAY_STATUS " +
              json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)
    log = safe_log if emit is None else emit

    def log_first_seen(phase, snapshot, expected_counts, index):
        """Log ONLY local first-receipt COUNTS; never raw timestamps or OHLC.

        A deployment/restart may leave old candles without receipt history.
        The presence of local timestamps does NOT prove independent market
        availability, licensing, or an admissible forward trading signal.
        """
        info=snapshot.get("firstSeenCoverage") if isinstance(snapshot,dict) else None
        if info is None:
            log({"event":"BIQUOTE_STAGE3_FIRST_SEEN_LEGACY_UNAVAILABLE",
                 "phase":phase,"dayIndex":index,
                 "firstAvailabilityVerified":False,**SAFE})
            return
        try:
            if (not isinstance(info,dict) or
                info.get("status")!="LOCAL_RECEIPTS_UNVERIFIED_NOT_TRADE_PROOF"
                or info.get("signal")!="WAIT" or info.get("executable") is not False
                or info.get("paperOrdersAllowed") is not False
                or info.get("sourceRightsVerified") is not False
                or info.get("brokerCalendarVerified") is not False
                or info.get("independentFirstAvailabilityVerified") is not False):
                raise ValueError("UNSAFE_FIRST_SEEN_COVERAGE")
            present,missing=info["recordedClosed"],info["unknownLegacyClosed"]
            if (not isinstance(present,dict) or not isinstance(missing,dict) or
                set(present)!={"M15","H1","H4"} or set(missing)!={"M15","H1","H4"}):
                raise ValueError("INVALID_FIRST_SEEN_COUNTERS")
            pairs={}
            for tf in ("M15","H1","H4"):
                ok=present[tf];unknown=missing[tf];n=expected_counts[tf]
                if (type(ok) is not int or type(unknown) is not int or
                    not 0<=ok<=n or unknown!=n-ok):
                    raise ValueError("CONTRADICTORY_FIRST_SEEN_COUNTERS")
                pairs[tf]={"locallyTimestamped":ok,"legacyUnknown":unknown}
            log({"event":"BIQUOTE_STAGE3_FIRST_SEEN_COVERAGE",
                 "phase":phase,"dayIndex":index,"frames":pairs,
                 "noFirstSeenBackfill":True,"firstAvailabilityVerified":False,
                 "brokerRightsVerified":False,"paperReady":False,**SAFE})
        except (ValueError,TypeError,KeyError):
            log({"event":"BIQUOTE_STAGE3_FIRST_SEEN_UNVERIFIED",
                 "phase":phase,"dayIndex":index,
                 "firstAvailabilityVerified":False,**SAFE})

    def log_gap_reference(phase, expected_counts, index):
        # Reopen only the sealed private archive, never any provider endpoint.
        # This is a GENERIC vendor-pause timing hypothesis, never broker
        # calendar verification or a reason to promote a trading signal.
        try:
            original = load_vault(str(folder))
            report = audit_closed_timestamp_reference({
                tf: [row["openTime"] for row in original["closed"][tf]]
                for tf in ("M15", "H1", "H4")})
            if report["status"] != "REFERENCE_ONLY_NOT_BROKER_VERIFIED":
                raise ValueError("BAD_REFERENCE_DIAGNOSTIC")
            parts = {}
            for tf in ("M15", "H1", "H4"):
                row = report["frames"][tf]
                if row["persistedClosed"] != expected_counts[tf]:
                    raise ValueError("COUNTER_DIAGNOSTIC_MISMATCH")
                parts[tf] = {
                    "unclassifiedMissingSlots": row["unclassifiedMissingSlots"],
                    "vendorPauseCandidateSlotsNotVerified":
                        row["vendorPauseCandidateSlotsNotVerified"],
                    "outsideVendorReferenceSlots": row["outsideVendorReferenceSlots"],
                    "unknownReferenceSlots": row["unknownReferenceSlots"]}
            log({"event": "BIQUOTE_STAGE3_VENDOR_REFERENCE_GAPS",
                 "phase": phase, "dayIndex": index, "frames": parts,
                 "genericVendorReferenceOnly": True,
                 "brokerSessionVerified": False, "gapsApproved": False, **SAFE})
        except (OSError, ValueError, TypeError, KeyError):
            log({"event": "BIQUOTE_STAGE3_REFERENCE_UNAVAILABLE",
                 "phase": phase, "dayIndex": index, **SAFE})
            return
        # Reuse this SAME sealed archive read to prove how many H1/H4 OHLC
        # bars are completely covered by M15; no raw OHLC or timestamps
        # enter logs. Uncovered bars must never count as agreements.
        try:
            tails = {}
            for tf in ("M15", "H1", "H4"):
                if len(original["closed"][tf]) != expected_counts[tf]:
                    raise ValueError("PARITY_ARCHIVE_COUNT_INCONSISTENT")
                tail = tail_contiguous(original["closed"][tf], WIDTH[tf])
                if original["closed"][tf] and not tail:
                    raise ValueError("PARITY_CLOSED_DATA_INVALID")
                tails[tf] = tail
            matches = overlaps_match(tails)
            evidence = {}
            for tf in ("H1", "H4"):
                compared = matches[tf]["fullyCoveredCompared"]
                wrong = matches[tf]["fullyCoveredDisagreed"]
                observed = len(tails[tf])
                if (type(compared) is not int or type(wrong) is not int or
                        not 0 <= wrong <= compared <= observed <= 48):
                    raise ValueError("PARITY_COUNTS_INVALID")
                evidence[tf] = {
                    "higherClosedExamined": observed,
                    "fullyCoveredCompared": compared,
                    "fullyCoveredDisagreed": wrong,
                    "notFullyCovered": observed - compared,
                }
            log({"event": "BIQUOTE_STAGE3_ARCHIVE_OHLC_OVERLAP",
                 "phase": phase, "dayIndex": index, "frames": evidence,
                 "brokerSessionVerified": False,
                 "sourceRightsVerified": False, "tradeEligible": False, **SAFE})
        except (OSError, ValueError, TypeError, KeyError):
            log({"event": "BIQUOTE_STAGE3_OHLC_OVERLAP_UNAVAILABLE",
                 "phase": phase, "dayIndex": index, **SAFE})
        # Price-free account of sampled BID/ASK midpoint consistency against
        # the *already sealed* CLOSED M15/H1/H4 ranges. Uses no extra GET or
        # disk read and never accepts a license or trading-ready claim.
        try:
            q=audit_closed_quote_mid_parity(original)
            statuses={"CONSISTENT_OBSERVED_SAMPLES_ONLY",
                      "NO_COMPARABLE_CLOSED_SAMPLES",
                      "OBSERVED_MID_OUTSIDE_CLOSED_OHLC"}
            if (q["status"] not in statuses or q["signal"]!="WAIT" or
                q["executable"] is not False or
                q["brokerRightsVerified"] is not False or
                q["brokerSessionCalendarVerified"] is not False or
                q["paperOrdersAllowed"] is not False or
                q["sourceQuoteSamples"]!=len(original["quoteObservations"])):
                raise ValueError("UNSAFE_MID_CANDLE_DIAGNOSTIC")
            safe_frames={}
            for tf in ("M15","H1","H4"):
                item=q["frames"][tf]
                count=expected_counts[tf]
                source_n=q["sourceQuoteSamples"]
                comparable=item["comparableQuoteSamples"]
                matching=item["withinClosedOHLC"]
                outside=item["outsideClosedOHLC"]
                unpaired=item["notInArchivedClosedBars"]
                distinct=item["distinctComparableClosedBars"]
                if (item["archivedClosedBars"]!=count or
                    any(type(n) is not int or n<0 for n in
                        (count,comparable,matching,outside,unpaired,distinct)) or
                    comparable+unpaired!=source_n or
                    matching+outside!=comparable or
                    distinct>min(count,comparable)):
                    raise ValueError("CONTRADICTORY_MID_CANDLE_COUNTS")
                safe_frames[tf]={
                    "comparableQuoteSamples":comparable,
                    "withinClosedOHLC":matching,
                    "outsideClosedOHLC":outside,
                    "notInArchivedClosedBars":unpaired,
                    "distinctComparableClosedBars":distinct}
            log({"event":"BIQUOTE_STAGE3_QUOTE_MID_CLOSED_RANGE",
                 "phase":phase,"dayIndex":index,
                 "status":q["status"],
                 "sourceQuoteSamples":q["sourceQuoteSamples"],
                 "frames":safe_frames,
                 "sourceRightsVerified":False,
                 "brokerSessionVerified":False,
                 "independentBrokerParityVerified":False,
                 "tradeEligible":False,**SAFE})
        except (OSError,ValueError,TypeError,KeyError,OverflowError):
            log({"event":"BIQUOTE_STAGE3_QUOTE_MID_RANGE_UNAVAILABLE",
                 "phase":phase,"dayIndex":index,**SAFE})
        # Same sealed private archive, only six fixed spread-bucket counts.
        # These sporadic quotes do NOT equal a continuous executable BBO
        # stream, broker commission schedule, or matched historical spread.
        try:
            spread = audited_sampled_spread_buckets(original)
            buckets = spread["buckets"]
            n = spread["sourceQuoteSamples"]
            if (spread["status"] not in ("OBSERVED_SPARSE_QUOTES_ONLY",
                                        "NO_RECORDED_QUOTES") or
                spread["mode"]!="BIQUOTE_PRIVATE_SAMPLED_SPREAD_COUNTS_V1" or
                spread["signal"]!="WAIT" or spread["executable"] is not False or
                spread["paperOrdersAllowed"] is not False or
                spread["liveOrdersAllowed"] is not False or
                spread["sourceRightsVerified"] is not False or
                spread["brokerCommissionSlippageVerified"] is not False or
                type(n) is not int or n!=len(original["quoteObservations"]) or
                not isinstance(buckets,dict) or set(buckets)!=set(BINS) or
                any(type(buckets[k]) is not int or buckets[k]<0 for k in BINS) or
                sum(buckets.values())!=n):
                raise ValueError("UNVERIFIED_OR_CONTRADICTORY_SPREAD_HISTOGRAM")
            log({"event":"BIQUOTE_STAGE3_SAMPLED_SPREAD_BUCKETS",
                 "phase":phase,"dayIndex":index,
                 "status":spread["status"],
                 "sourceQuoteSamples":n,"buckets":dict(buckets),
                 "quoteSamplesSparseNotExecutionBBO":True,
                 "brokerContractFeesVerified":False,
                 "independentBrokerParityVerified":False,
                 "tradeEligible":False,**SAFE})
        except (OSError,ValueError,TypeError,KeyError,OverflowError):
            log({"event":"BIQUOTE_STAGE3_SPREAD_BUCKETS_UNAVAILABLE",
                 "phase":phase,"dayIndex":index,**SAFE})
        # One sealed snapshot already in memory, no extra provider GETs.
        # Quote receipt intervals may include legitimate closed-session pauses.
        # We measure observed sampling cadence only; NEVER infer broker uptime.
        try:
            cadence = audit_quote_cadence(original)
            bins=cadence["intervalBins"]
            lag_bins=cadence["quoteReceiptLagBins"]
            n=cadence["sourceQuoteSamples"]
            gaps=cadence["observedIntervals"]
            if (cadence["status"] not in ("SPARSE_RECEIPT_CADENCE_OBSERVED_ONLY",
                                         "NO_RECORDED_QUOTES") or
                cadence["mode"]!="BIQUOTE_PRIVATE_SAMPLED_QUOTE_CADENCE_COUNTS_V1" or
                cadence["signal"]!="WAIT" or cadence["executable"] is not False or
                cadence["paperOrdersAllowed"] is not False or
                cadence["liveOrdersAllowed"] is not False or
                cadence["brokerCalendarVerified"] is not False or
                cadence["continuousMarketDataVerified"] is not False or
                cadence["missingSamplesAreMarketOutageProof"] is not False or
                type(n) is not int or n!=len(original["quoteObservations"]) or
                type(gaps) is not int or gaps!=max(0,n-1) or
                not isinstance(bins,dict) or set(bins)!=set(INTERVAL_BINS) or
                not isinstance(lag_bins,dict) or set(lag_bins)!=set(LAG_BINS) or
                any(type(v) is not int or v<0 for v in bins.values()) or
                any(type(v) is not int or v<0 for v in lag_bins.values()) or
                sum(bins.values())!=gaps or sum(lag_bins.values())!=n):
                raise ValueError("UNVERIFIED_SAMPLED_QUOTE_CADENCE")
            log({"event":"BIQUOTE_STAGE3_QUOTE_RECEIPT_CADENCE",
                 "phase":phase,"dayIndex":index,
                 "status":cadence["status"],
                 "sourceQuoteSamples":n,
                 "observedIntervals":gaps,
                 "intervalBins":dict(bins),
                 "quoteReceiptLagBins":dict(lag_bins),
                 "brokerSessionVerified":False,
                 "sampledQuotesNotContinuousMarketFeed":True,
                 "missingSlotsNotBrokerOutageProof":True,
                 "tradeEligible":False,**SAFE})
        except (OSError,ValueError,TypeError,KeyError,OverflowError):
            log({"event":"BIQUOTE_STAGE3_CADENCE_UNAVAILABLE",
                 "phase":phase,"dayIndex":index,**SAFE})

    completed = skipped = 0
    state = "BOUNDED_REVIEW_FINISHED"
    startup_checked = False
    for index in range(days):
        start = anchor + dt.timedelta(days=index)
        end = start + dt.timedelta(seconds=WINDOW_SECONDS)
        now = _utc(get_time())
        if now >= end:
            skipped += 1
            log({"event": "BIQUOTE_SEVEN_DAY_EXPIRED_DAY_SKIPPED", "dayIndex": index, **SAFE})
            continue
        # observe_24h rejects starts >15 minutes in the future. Wait on the
        # private worker only; no HTTP traffic, archive writes or busy polling.
        while now < start - dt.timedelta(minutes=14):
            do_sleep(min(60.0, (start - dt.timedelta(minutes=14) - now).total_seconds()))
            next_time = _utc(get_time())
            if next_time <= now:
                raise ValueError("NON_ADVANCING_REVIEW_CLOCK")
            now = next_time
        try:
            # inspect_metadata loads the on-disk sealed content and checks the
            # SHA-256 envelope and owner-only permissions on every restart.
            vault_status = metadata(str(folder))
            cap = capacity_readiness(vault_status)
        except (OSError, ValueError, TypeError, KeyError):
            state = "VAULT_METADATA_READ_BLOCKED"
            log({"event": "BIQUOTE_SEVEN_DAY_VAULT_AUDIT_BLOCKED",
                 "status": state, "dayIndex": index, **SAFE})
            break
        if not startup_checked:
            startup_checked = True
            # Only count fields already normalized by capacity_readiness.
            counts = {tf: cap["closedBarHardCapEach"] -
                      cap["closedBarsRemaining"][tf] for tf in ("M15","H1","H4")}
            log({"event": "BIQUOTE_SEVEN_DAY_VAULT_REOPEN_AUDIT",
                 "status": "SEALED_VAULT_READABLE",
                 "dayIndex": index, "closedBarCounts": counts,
                 "previouslyStoredQuoteSamples": cap["quoteSamplesUsed"],
                 "previouslyStoredData": bool(cap["quoteSamplesUsed"] or any(counts.values())),
                 "capacityStatus": cap["status"], **SAFE})
            log_first_seen("RESTART", vault_status, counts, index)
            log_gap_reference("RESTART", counts, index)
        if (cap["status"] == "CAPACITY_LIMIT_REACHED"
                or cap["quoteSamplesRemaining"] < MAX_SAMPLES
                or any(n < (96 if tf == "M15" else 24 if tf == "H1" else 6)
                       for tf, n in cap["closedBarsRemaining"].items())):
            state = "CAPACITY_REVIEW_REQUIRED"
            log({"event": "BIQUOTE_SEVEN_DAY_CAPACITY_STOP", "dayIndex": index, **SAFE})
            break

        def only_shared_probe():
            def private_sink(packet, received):
                value = received.isoformat(timespec="milliseconds").replace("+00:00", "Z")
                outcome = archive(str(folder), packet, received_utc=value)
                # Metadata-only progress after a truly NEW closed bar.
                # No second provider call, no OHLC, quotes, tokens, paths,
                # raw exception messages, market decisions or orders in logs.
                if isinstance(outcome, dict):
                    additions = outcome.get("newClosedBars")
                    if (isinstance(additions, dict) and
                            set(additions) == {"M15", "H1", "H4"} and
                            all(type(additions[tf]) is int and 0 <= additions[tf] <= 1000
                                for tf in ("M15", "H1", "H4")) and
                            any(additions.values())):
                        try:
                            fresh = metadata(str(folder))
                            if (not isinstance(fresh, dict) or
                                    fresh.get("status") != "PRIVATE_FORWARD_VAULT_METADATA_ONLY" or
                                    fresh.get("signal") != "WAIT" or
                                    fresh.get("executable") is not False or
                                    fresh.get("tradeSignalReady") is not False):
                                raise ValueError("UNTRUSTED_VAULT_METADATA")
                            details = {}
                            for tf in ("M15", "H1", "H4"):
                                count = fresh["counts"][tf]
                                cov = fresh["forwardCoverage"][tf]
                                tail = cov["latestContiguousBars"]
                                gaps = cov["unclassifiedGapPairs"]
                                missing = cov["unclassifiedMissingSlots"]
                                if (type(count) is not int or not 0 <= count <= 45000 or
                                        type(tail) is not int or not 0 <= tail <= count or
                                        type(gaps) is not int or not 0 <= gaps <= count or
                                        type(missing) is not int or not 0 <= missing <= 4500000 or
                                        cov["closedBars"] != count):
                                    raise ValueError("INCONSISTENT_VAULT_COUNTERS")
                                details[tf] = {
                                    "persistedClosed": count,
                                    "contiguousClosed": min(tail, 48),
                                    "unclassifiedGapPairs": gaps,
                                    "unclassifiedMissingSlots": missing}
                            log({"event": "BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS",
                                 "dayIndex": index, "frames": details,
                                 "h4RemainingUntil21": max(0, 21-details["H4"]["contiguousClosed"]),
                                 "sourceRightsVerified": False,
                                 "independentBrokerSessionVerified": False,
                                 "v3TradeQualified": False, **SAFE})
                            stable_counts={
                                tf: details[tf]["persistedClosed"]
                                for tf in ("M15", "H1", "H4")}
                            log_first_seen("NEW_CLOSED_BAR", fresh,
                                           stable_counts,index)
                            log_gap_reference("NEW_CLOSED_BAR",stable_counts,index)
                        except (OSError, ValueError, TypeError, KeyError):
                            log({"event": "BIQUOTE_STAGE3_METADATA_UNAVAILABLE",
                                 "dayIndex": index, **SAFE})
                return outcome
            return source_probe(private_snapshot_sink=private_sink)

        log({"event": "BIQUOTE_SEVEN_DAY_WINDOW_STARTED", "dayIndex": index, **SAFE})
        report = observer(start, probe=only_shared_probe)
        if not isinstance(report, dict) or report.get("signal") != "WAIT" or report.get("executable") is not False:
            state = "REPORT_CONTRACT_REJECTED"
            break
        if report.get("completed24hWindow") is not True:
            state = "INCOMPLETE_WINDOW"
            break
        completed += 1
        log({"event": "BIQUOTE_SEVEN_DAY_WINDOW_FINISHED", "dayIndex": index, **SAFE})
    return {"mode": "BIQUOTE_BOUNDED_SEVEN_DAY_PRIVATE_REVIEW",
            "status": state, "windowDays": days, "windowsCompleted": completed,
            "windowsExpiredWithoutReplay": skipped, "sourceQualifiedForTrading": False,
            "independentBrokerRightsVerified": False,
            "independentBrokerCalendarVerified": False,
            "netPaperExpectancyVerified": False,
            "dataBasis": "MID_POSSIBLY_BID_SEEDED", **SAFE}
