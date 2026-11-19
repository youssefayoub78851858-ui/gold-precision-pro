"""Research-only paper trading admission check: always BLOCKED before licensed feed.

This is NOT an execution service and never initializes an account or order.
It only converts private WAIT audit/status signals into a small, safe UI report.
Actual paper orders require a separately approved research data pipeline,
a verified feed, completed risk gates, and an explicit later activation.
"""
from __future__ import annotations

from paper_cost_preflight import cost_readiness

ALLOWED = {
    "NOT_CONNECTED", "BLOCKED", "WAIT_STALE", "WAIT_NO_VERIFIED_QUOTE",
    "WAIT_REVIEW_OBSERVATION_ONLY",
}
AUDIT = {"AUDIT_DISABLED", "AUDIT_NOT_STARTED", "AUDIT_OK",
         "AUDIT_STALE", "AUDIT_UNAVAILABLE"}
MIN_CLOSED_BARS = {"M15": 50, "H1": 50, "H4": 50}

def assess_paper_gate(monitor: object, audit: object) -> dict:
    reasons = ["PAPER_LIVE_ACTIVATION_NOT_APPROVED",
               "SOURCE_LICENSE_AND_HISTORY_NOT_VERIFIED",
               "RISK_AND_BROKER_COSTS_NOT_VERIFIED"]
    data = monitor if isinstance(monitor, dict) else {}
    audit = audit if isinstance(audit, dict) else {}
    if (data.get("status") != "WAIT_EODHD_INTAKE"
            or data.get("dataStatus") not in ALLOWED
            or data.get("signal") != "WAIT"
            or data.get("executable") is not False
            or data.get("researchEligible") is not False
            or data.get("paperRunning") is not False
            or data.get("engineStatus") != "NOT_INVOKED"
            or data.get("sourceRequestsMade") != 0):
        reasons.append("MARKET_RESEARCH_CONTRACT_UNVERIFIED")
    if data.get("dataStatus") != "WAIT_REVIEW_OBSERVATION_ONLY":
        reasons.append("EODHD_SOURCE_NOT_READY")
    counts = data.get("closedBarCounts")
    if (not isinstance(counts, dict)
            or any(not isinstance(counts.get(tf), int) or isinstance(counts.get(tf), bool)
                   or counts[tf] < required for tf, required in MIN_CLOSED_BARS.items())):
        reasons.append("CLOSED_MULTITIMEFRAME_HISTORY_INCOMPLETE")
    if (audit.get("status") not in AUDIT or audit.get("status") != "AUDIT_OK"
            or audit.get("signal") != "WAIT"
            or audit.get("executable") is not False
            or audit.get("paperRunning") is not False
            or not isinstance(audit.get("ageSeconds"), int)
            or isinstance(audit.get("ageSeconds"), bool)
            or not 0 <= audit["ageSeconds"] <= 120):
        reasons.append("MONITOR_HEARTBEAT_UNVERIFIED")
    # Genuine market-data entitlements, risk approval, and paper execution are
    # never inferred from an uploaded file or the appearance of 50 bars.
    return {
        "mode": "PAPER_ADMISSION_REVIEW_ONLY",
        "status": "BLOCKED",
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "paperOrdersAllowed": False,
        "paperRunning": False,
        "ledgerCreatedByGate": False,
        "simulationEvidenceIsLive": False,
        "reasonCodes": reasons,
        "costReadiness": cost_readiness(),
    }


def biquote_history_readiness(closed_counts: object, contiguous_counts: object = None) -> dict:
    """Safe count-only preflight, never permission to trade or gap-bridging.

    A 50-bar floor matches the existing paper-history baseline. Passing
    counts cannot establish the source license, broker calendar, independent
    costs or uninterrupted broker sessions; none are promoted here.
    """
    frames = ("M15", "H1", "H4")
    valid = (isinstance(closed_counts, dict)
             and set(closed_counts) == set(frames)
             and all(type(closed_counts.get(tf)) is int
                     and 0 <= closed_counts[tf] <= 45000 for tf in frames))
    counts = {tf: closed_counts[tf] if valid else None for tf in frames}
    missing = {tf: max(0, 50 - counts[tf]) if valid else None for tf in frames}
    enough = valid and all(n == 0 for n in missing.values())
    # A saved historical bar does not imply that the latest H4 sequence
    # covers 50 consecutive closed market bars. No independent broker
    # session/calendar, timestamp or execution attestation is inferred.
    contiguous_valid = (valid and isinstance(contiguous_counts, dict)
                        and set(contiguous_counts) == set(frames)
                        and all(type(contiguous_counts.get(tf)) is int
                                and 0 <= contiguous_counts[tf] <= counts[tf]
                                for tf in frames))
    contiguous = {tf: contiguous_counts[tf] if contiguous_valid else None
                  for tf in frames}
    missing_contiguous = {
        tf: max(0, 50 - contiguous[tf]) if contiguous_valid else None
        for tf in frames
    }
    contiguous_enough = contiguous_valid and all(
        n == 0 for n in missing_contiguous.values())
    return {
        "mode": "BIQUOTE_PAPER_HISTORY_COUNT_PREFLIGHT_ONLY",
        "status": ("UNVERIFIED_CLOSED_HISTORY" if not valid else
                   "COUNT_FLOOR_REACHED_NOT_PAPER_READY" if enough else
                   "BELOW_50_CLOSED_BARS_PER_FRAME"),
        "signal": "WAIT", "executable": False, "paperOrdersAllowed": False,
        "minimumClosedBarsEachFrame": 50,
        "closedCounts": counts, "missingUntil50": missing,
        "countMinimumMet": bool(enough),
        "contiguousClosedCounts": contiguous,
        "missingContiguousUntil50": missing_contiguous,
        "contiguousCountsVerifiedWithinArchive": bool(contiguous_valid),
        "contiguousCountMinimumMet": bool(contiguous_enough),
        "50BarHistoryFullyQualified": False,
        "brokerSessionCalendarVerified": False,
        "independentSourceRightsVerified": False,
        "executionCostsVerified": False,
        "sourceQuotesNotBrokerFills": True,
    }


def assess_biquote_paper_gate(source_audit: object, research_intake: object,
                              closed_counts: object = None,
                              contiguous_counts: object = None) -> dict:
    """Fail-closed BiQuote paper-trading admission. Never constructs a ledger."""
    audit = source_audit if isinstance(source_audit, dict) else {}
    intake = research_intake if isinstance(research_intake, dict) else {}
    reasons = [
        "PAPER_ACTIVATION_NOT_APPROVED",
        "BIQUOTE_SOURCE_AND_UNDERLYING_RIGHTS_UNVERIFIED",
        "BIQUOTE_HISTORICAL_BID_ASK_BASIS_UNVERIFIED",
        "INDEPENDENT_SESSION_AND_BROKER_PARITY_UNVERIFIED",
        "BROKER_COST_AND_RISK_APPROVAL_MISSING",
    ]
    if audit.get("ohlcStructuralChecksPassed") is not True:
        reasons.append("BIQUOTE_STRUCTURAL_AUDIT_FAILED")
    if intake.get("status") != "ADMISSIBLE_FOR_RESEARCH_ONLY":
        reasons.append("RESEARCH_INTAKE_BLOCKED")
    history = biquote_history_readiness(closed_counts, contiguous_counts)
    if not history["contiguousCountsVerifiedWithinArchive"]:
        reasons.append("BIQUOTE_CONTIGUOUS_PAPER_HISTORY_UNVERIFIED")
    elif not history["contiguousCountMinimumMet"]:
        reasons.append("BIQUOTE_CONTIGUOUS_PAPER_50_BAR_MINIMUM_INCOMPLETE")
    if history["status"] == "UNVERIFIED_CLOSED_HISTORY":
        reasons.append("BIQUOTE_FORWARD_HISTORY_UNAVAILABLE")
    elif not history["countMinimumMet"]:
        reasons.append("BIQUOTE_PAPER_HISTORY_50_BAR_MINIMUM_INCOMPLETE")
    return {
        "mode": "PAPER_ADMISSION_REVIEW_ONLY", "provider": "BiQuote",
        "status": "BLOCKED", "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "paperRunning": False, "ledgerCreatedByGate": False,
        "sourceRequestsMade": 0, "reasonCodes": reasons,
        "historyReadiness": history,
        "costReadiness": cost_readiness(),
    }
