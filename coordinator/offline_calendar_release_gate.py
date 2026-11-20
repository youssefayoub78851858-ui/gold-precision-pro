"""Fail-closed calendar-release chronology audit OUTSIDE the frozen V2 engine.

Offline import and time comparisons only. Source entitlement is caller-claimed
and not independently verified. Never feeds paper/live order admission.
"""
from __future__ import annotations

from ultimate_connectors import utc, validate

# Treat zero as a released value, not as an absent placeholder.
RESULT_FIELDS = (
    "actual", "actualValue", "actual_value", "surprise", "surpriseValue",
    "surprise_value", "revisedActual", "revised_actual", "revision",
)


def _safe(status, reason):
    return {
        "mode": "OFFLINE_CALENDAR_RELEASE_QUARANTINE",
        "status": status, "reason": reason, "signal": "WAIT",
        "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "sourceRightsIndependentlyVerified": False,
        "publicationTimeIndependentlyVerified": False,
        "independentHoldoutValidated": False,
        "providerRequestsMade": 0, "brokerOrdersSent": 0,
        "scheduledEvents": 0, "historicalEvents": 0,
    }


def inspect_calendar_release(record, *, as_of_utc):
    """Audit whether an export contains event results before publication.

    This protective wrapper does not modify ultimate_connectors.py (frozen).
    Even a valid return is only descriptive evidence, never an approval.
    """
    if not isinstance(record, dict):
        return _safe("BLOCKED", "INVALID_OFFLINE_CALENDAR_EXPORT")
    try:
        validate("calendar", record)
        as_of = utc(as_of_utc)
        available = utc(record["availableUTC"])
        if available > as_of:
            return _safe("BLOCKED", "EXPORT_NOT_AVAILABLE_AT_AUDIT_CUTOFF")
        upcoming = historical = 0
        for event in record["events"]:
            released = utc(event["timeUTC"])
            if released > available:
                if any(event.get(key) is not None for key in RESULT_FIELDS):
                    return _safe("BLOCKED", "PRE_RELEASE_ACTUAL_SURPRISE_OR_REVISION")
                if str(event.get("status", "")).strip().lower() in (
                    "released", "completed", "published_actual"
                ):
                    return _safe("BLOCKED", "PRE_RELEASE_COMPLETED_EVENT_CLAIM")
                upcoming += 1
            else:
                historical += 1
        out = _safe("UNATTESTED_CHRONOLOGY_ONLY",
                    "LICENSE_RELEASE_CLOCK_AND_INDEPENDENT_SOURCE_NOT_ATTESTED")
        out["scheduledEvents"] = upcoming
        out["historicalEvents"] = historical
        return out
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return _safe("BLOCKED", "INVALID_OR_UNAUTHORIZED_OFFLINE_CALENDAR_EXPORT")
