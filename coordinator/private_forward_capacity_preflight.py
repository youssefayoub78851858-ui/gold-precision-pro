"""Owner-only, price-free capacity preflight for the BiQuote forward vault.

This does not rotate/delete archived quotes, fill missing bars, fetch a
provider, or permit an order. It reports the actual current hard caps so
long-running private capture doesn't silently stop after filling storage.
"""
from __future__ import annotations

from biquote_private_forward_vault import (
    FRAMES_ORDER, MAX_CANDLES_PER_FRAME, MAX_QUOTE_SAMPLES,
)

def _count(value, maximum):
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError("UNTRUSTED_CAPACITY_COUNT")
    return value

def capacity_readiness(metadata):
    if (not isinstance(metadata, dict) or
        metadata.get("status") != "PRIVATE_FORWARD_VAULT_METADATA_ONLY" or
        metadata.get("signal") != "WAIT" or
        metadata.get("executable") is not False or
        metadata.get("paperOrdersAllowed") is not False or
        metadata.get("tradeSignalReady") is not False or
        not isinstance(metadata.get("counts"), dict) or
        set(metadata["counts"]) != set(FRAMES_ORDER)):
        raise ValueError("PRIVATE_METADATA_NOT_ADMISSIBLE")
    used_quotes = _count(metadata.get("quoteSamples"), MAX_QUOTE_SAMPLES)
    bars = {tf: _count(metadata["counts"][tf], MAX_CANDLES_PER_FRAME)
            for tf in FRAMES_ORDER}
    remaining = {tf: MAX_CANDLES_PER_FRAME - bars[tf]
                 for tf in FRAMES_ORDER}
    quote_remaining = MAX_QUOTE_SAMPLES - used_quotes
    # Assume only an ILLUSTRATIVE two-minute observation cadence; real quote
    # duplication, market closures and runtime restarts make this non-forecast.
    at_2min_hours = round(quote_remaining * 2 / 60, 1)
    warn = (
        used_quotes >= MAX_QUOTE_SAMPLES * 0.8 or
        any(bars[tf] >= MAX_CANDLES_PER_FRAME * 0.8
            for tf in FRAMES_ORDER)
    )
    exhausted = quote_remaining == 0 or any(x == 0 for x in remaining.values())
    status = ("CAPACITY_LIMIT_REACHED" if exhausted else
              "CAPACITY_WARNING" if warn else "CAPACITY_HEADROOM")
    return {
        "mode": "PRIVATE_FORWARD_CAPACITY_METADATA_ONLY",
        "status": status, "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "sourceEntitlementVerified": False,
        "archiveActivationAllowed": False,
        "autoDeleteOrRotateAllowed": False,
        "marketDataExposed": False, "providerRequestsMade": 0,
        "quoteSamplesUsed": used_quotes,
        "quoteSamplesHardCap": MAX_QUOTE_SAMPLES,
        "quoteSamplesRemaining": quote_remaining,
        "closedBarsRemaining": remaining,
        "closedBarHardCapEach": MAX_CANDLES_PER_FRAME,
        "illustrativeRemainingHoursAtOneUniqueQuoteEvery2min": at_2min_hours,
        "projectionIsMarketDataOrUptimeForecast": False,
        "reasonCodes": (
            ["CAPACITY_REQUIRES_OWNER_RETENTION_DECISION"] if exhausted else
            ["CAPACITY_WARNING_REVIEW_BEFORE_CAPTURE_CONTINUES"] if warn else
            ["CAPACITY_WITHIN_STATIC_HARD_LIMITS"]
        ),
    }
