"""Zero-network, synthetic-only XAU/USD paper cost and risk diagnostic.

This pure preflight never reads a broker, places an order, or verifies a fee
schedule. Its arithmetic is useful for testing risk controls only; guessed
contract sizes and spreads must not be admitted as live evidence.
"""
from __future__ import annotations
import math

REQUIRED = (
    "contractOuncesPerLot", "lots", "spreadUsdPerOunce",
    "entrySlippageUsdPerOunce", "exitSlippageUsdPerOunce",
    "commissionRoundTripUsdPerLot", "stopDistanceUsdPerOunce",
    "targetNetUsd", "equityUsd", "riskFraction", "dailyLossFraction",
    "dailyLossUsedUsd",
)
BLOCKERS = (
    "BROKER_CONTRACT_AND_LOT_SPEC_UNVERIFIED",
    "LIVE_BID_ASK_SPREAD_EVIDENCE_MISSING",
    "COMMISSION_AND_SLIPPAGE_EVIDENCE_MISSING",
    "RISK_BUDGET_AND_STOP_DISTANCE_UNVERIFIED",
)

def cost_readiness() -> dict:
    """Expose only requirements, not invented quotes or broker credentials."""
    return {
        "mode": "BROKER_COST_EVIDENCE_REVIEW_ONLY",
        "status": "BLOCKED",
        "signal": "WAIT",
        "executable": False,
        "modelAvailable": True,
        "realBrokerFeesVerified": False,
        "realBidAskVerified": False,
        "riskBudgetVerified": False,
        "ordersAllowed": False,
        "sampleTradeExecuted": False,
        "reasonCodes": list(BLOCKERS),
    }

def synthetic_scenario_cost(values: dict) -> dict:
    """Evaluate explicit hypothetical cost/risk inputs only.

    Required input provenance: SYNTHETIC_TEST_ONLY, never real broker data.
    Spread is charged ONCE per round trip (ask BUY entry / ask SELL exit).
    Slippage is applied adversely at both entry and exit. Commission is
    an explicitly supplied ROUND-TRIP cost per lot, with no hidden defaults.
    """
    if not isinstance(values, dict) or values.get("dataOrigin") != "SYNTHETIC_TEST_ONLY":
        raise ValueError("Only labelled offline synthetic inputs are accepted")
    if not all(name in values for name in REQUIRED):
        raise ValueError("Missing broker cost, contract or risk assumption")
    if set(values) != set(REQUIRED) | {"dataOrigin"}:
        raise ValueError("Unexpected or ambiguous synthetic assumption")
    for name in REQUIRED:
        value = values[name]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise ValueError("Nonfinite or non-numeric cost assumption")
    for name in ("contractOuncesPerLot", "lots", "stopDistanceUsdPerOunce",
                 "targetNetUsd", "equityUsd"):
        if values[name] <= 0:
            raise ValueError("Strictly positive quantity required")
    if any(values[name] < 0 for name in (
        "spreadUsdPerOunce", "entrySlippageUsdPerOunce",
        "exitSlippageUsdPerOunce", "commissionRoundTripUsdPerLot",
        "dailyLossUsedUsd"
    )):
        raise ValueError("Negative trading costs or losses are invalid")
    if not 0 < values["riskFraction"] <= 0.005:
        raise ValueError("Risk fraction exceeds research ceiling 0.5 percent")
    if not 0 < values["dailyLossFraction"] <= 0.02:
        raise ValueError("Daily loss fraction exceeds research ceiling 2 percent")
    if values["lots"] > 10 or values["contractOuncesPerLot"] > 1000:
        raise ValueError("Unbounded lot/contract assumption")
    ounces = values["contractOuncesPerLot"] * values["lots"]
    spread = values["spreadUsdPerOunce"] * ounces
    slippage = (values["entrySlippageUsdPerOunce"]
                + values["exitSlippageUsdPerOunce"]) * ounces
    commission = values["commissionRoundTripUsdPerLot"] * values["lots"]
    friction = spread + slippage + commission
    gross_stop = values["stopDistanceUsdPerOunce"] * ounces
    risk_budget = min(
        values["equityUsd"] * values["riskFraction"],
        max(0.0, values["equityUsd"] * values["dailyLossFraction"]
            - values["dailyLossUsedUsd"]),
    )
    total_loss = gross_stop + friction
    result = {
        "mode": "OFFLINE_SYNTHETIC_COST_SCENARIO",
        "dataOrigin": "SYNTHETIC_TEST_ONLY",
        "status": "BLOCKED",
        "signal": "WAIT",
        "executable": False,
        "ordersAllowed": False,
        "spreadRoundTripUsd": round(spread, 8),
        "slippageRoundTripUsd": round(slippage, 8),
        "commissionRoundTripUsd": round(commission, 8),
        "totalFrictionUsd": round(friction, 8),
        "lossAtStopInclCostsUsd": round(total_loss, 8),
        "riskBudgetUsd": round(risk_budget, 8),
        "targetGrossUsdToNet": round(values["targetNetUsd"] + friction, 8),
        "priceMoveUsdPerOunceToNetTarget":
            round((values["targetNetUsd"] + friction) / ounces, 8),
        "hypotheticalRiskWithinBudget": total_loss <= risk_budget,
        "realBrokerEvidenceVerified": False,
        "paperTradingApproved": False,
    }
    if not all(math.isfinite(v) for v in result.values() if isinstance(v, float)):
        raise ValueError("Out-of-range financial arithmetic")
    return result
