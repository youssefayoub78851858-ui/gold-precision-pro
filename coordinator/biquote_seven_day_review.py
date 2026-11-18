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
from private_forward_capacity_preflight import capacity_readiness

UTC = dt.timezone.utc
DAYS = 7
SEVEN_DAY_ENV = "GPP_BIQUOTE_7DAY_FORWARD_REVIEW"
SEVEN_DAY_VALUE = "APPROVED_SEVEN_DAYS_READONLY_NO_TRADING"
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
    if anchor != START or type(days) is not int or not 1 <= days <= DAYS:
        raise ValueError("HOLDOUT_ANCHOR_OR_WINDOW_INVALID")
    get_time = clock or (lambda: dt.datetime.now(UTC))
    do_sleep = sleep or time.sleep
    # Default logs contain fixed metadata only. Private quote prices, source
    # JSON and full vault paths never enter Render application logs.
    def safe_log(record):
        print("BIQUOTE_SEVEN_DAY_STATUS " +
              json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)
    log = safe_log if emit is None else emit

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

    completed = skipped = 0
    state = "BOUNDED_REVIEW_FINISHED"
    startup_checked = False
    for index in range(days):
        start = START + dt.timedelta(days=index)
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
            cap = capacity_readiness(metadata(str(folder)))
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
                            log_gap_reference("NEW_CLOSED_BAR", {
                                tf: details[tf]["persistedClosed"]
                                for tf in ("M15", "H1", "H4")}, index)
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
