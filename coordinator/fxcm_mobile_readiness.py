"""FXCM availability summary for the private review dashboard.

Only reports static, unresolved licensing and feed-connection gates.
It never opens a broker account, loads the SDK, reads secrets or sends orders.
No market prices, example fixtures or user-supplied approval flags are accepted.
"""
from __future__ import annotations

REASONS = (
    "FXCM_EULA_AND_CLOUD_RIGHTS_UNVERIFIED",
    "FXCM_DEMO_READ_ONLY_ENTITLEMENT_UNVERIFIED",
    "FXCM_REAL_XAUUSD_BID_ASK_NOT_CONNECTED",
    "FXCM_UTC_SESSION_AND_HISTORY_PARITY_UNVERIFIED",
)


def read_fxcm_review_status() -> dict:
    """Static offline-review facts, not real-time broker availability."""
    return {
        "provider": "FXCM",
        "mode": "OFFLINE_PREPARATION_ONLY",
        "status": "WAIT_FXCM_NOT_CONNECTED",
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "paperOrdersAllowed": False,
        "tradingEnabled": False,
        "providerAccessStarted": False,
        "sdkLoaded": False,
        "sourceRequestsMade": 0,
        "credentialsRead": 0,
        "livePricesAvailable": False,
        "accountPermissionsVerified": False,
        "licenseVerified": False,
        "validatedClosedBarCounts": {"M15": 0, "H1": 0, "H4": 0},
        "blockingReasons": list(REASONS),
    }
