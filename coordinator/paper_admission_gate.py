"""Research-only paper trading admission check: always BLOCKED before licensed feed.

This is NOT an execution service and never initializes an account or order.
It only converts private WAIT audit/status signals into a small, safe UI report.
Actual paper orders require a separately approved research data pipeline,
a verified feed, completed risk gates, and an explicit later activation.
"""
from __future__ import annotations

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
    }
