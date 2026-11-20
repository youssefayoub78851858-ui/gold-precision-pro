"""Isolated synthetic broker-cost stress gate; no account or feed I/O.

A single benign spread assumption is not an adequate risk test. This unit
replays the frozen paper_cost_preflight arithmetic under adverse friction.
It never determines actual broker costs or authorizes simulated/real orders.
"""
from __future__ import annotations

import math
import re

from paper_cost_preflight import REQUIRED, synthetic_scenario_cost

MODE = "OFFLINE_SYNTHETIC_BROKER_FRICTION_STRESS_V1"
FACTORS = (
    "spreadMultiplier", "entrySlippageMultiplier",
    "exitSlippageMultiplier", "commissionMultiplier"
)
MAX_SCENARIOS = 8


def _blocked(reason):
    return {
        "mode": MODE, "status": "BLOCKED", "reason": reason,
        "dataOrigin": "SYNTHETIC_TEST_ONLY",
        "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
        "brokerEvidenceVerified": False, "independentSpreadVerified": False,
        "independentCommissionVerified": False,
        "forwardPerformanceValidated": False, "tradingApproved": False,
        "brokerRequestsMade": 0, "ordersSent": 0,
        "scenariosChecked": 0, "stressRiskWithinBudget": False,
        "results": [],
    }


def inspect_stress(packet):
    """Return sanitized risk math without exposing input or approving trades."""
    result = _blocked("INVALID_OR_UNATTESTED_SYNTHETIC_SCENARIOS")
    try:
        if not isinstance(packet, dict) or set(packet) != {
                "dataOrigin", "baseline", "scenarios"}:
            return result
        if packet["dataOrigin"] != "SYNTHETIC_TEST_ONLY":
            return result
        baseline = packet["baseline"]
        if not isinstance(baseline, dict) or set(baseline) != set(REQUIRED) | {"dataOrigin"}:
            return result
        if baseline["dataOrigin"] != "SYNTHETIC_TEST_ONLY":
            return result
        variants = packet["scenarios"]
        if not isinstance(variants, list) or not 1 <= len(variants) <= MAX_SCENARIOS:
            return result
        names = set()
        adverse = False
        for variant in variants:
            if not isinstance(variant, dict) or set(variant) != set(FACTORS) | {"name"}:
                return result
            name = variant["name"]
            if not isinstance(name, str) or not re.fullmatch(
                    r"[a-z][a-z0-9_]{0,31}", name) or name in names:
                return result
            names.add(name)
            for field in FACTORS:
                value = variant[field]
                if (type(value) not in (float, int) or not math.isfinite(value)
                        or not 1 <= value <= 10):
                    return result
                adverse = adverse or value > 1
        if not adverse:
            return _blocked("NO_ADVERSE_COST_SCENARIO")
        base = synthetic_scenario_cost(baseline)
        reports = []
        for variant in variants:
            stressed = dict(baseline)
            stressed["spreadUsdPerOunce"] *= variant["spreadMultiplier"]
            stressed["entrySlippageUsdPerOunce"] *= variant["entrySlippageMultiplier"]
            stressed["exitSlippageUsdPerOunce"] *= variant["exitSlippageMultiplier"]
            stressed["commissionRoundTripUsdPerLot"] *= variant["commissionMultiplier"]
            calc = synthetic_scenario_cost(stressed)
            reports.append({
                "scenario": variant["name"],
                "modeledFrictionUsd": calc["totalFrictionUsd"],
                "stopLossPlusCostsUsd": calc["lossAtStopInclCostsUsd"],
                "riskBudgetUsd": calc["riskBudgetUsd"],
                "hypotheticalRiskWithinBudget": calc["hypotheticalRiskWithinBudget"],
                "frictionConsumesFullRiskBudget": calc["frictionConsumesFullRiskBudget"],
            })
        worst = max(reports, key=lambda item: item["stopLossPlusCostsUsd"])
        within = base["hypotheticalRiskWithinBudget"] and all(
            item["hypotheticalRiskWithinBudget"] for item in reports)
        return {
            **result,
            "status": ("UNATTESTED_SYNTHETIC_RISK_WITHIN_BUDGET"
                       if within else "BLOCKED_BY_SYNTHETIC_COST_STRESS"),
            "reason": ("SOURCE_RIGHTS_COSTS_AND_FORWARD_RESULTS_NOT_PROVEN"
                       if within else "MODELED_STOP_LOSS_EXCEEDS_RISK_BUDGET"),
            "scenariosChecked": len(reports),
            "stressRiskWithinBudget": within,
            "baselineFrictionUsd": base["totalFrictionUsd"],
            "baselineRiskBudgetUsd": base["riskBudgetUsd"],
            "worstScenario": worst["scenario"],
            "worstModeledStopLossPlusCostsUsd": worst["stopLossPlusCostsUsd"],
            "results": reports,
        }
    except (ValueError, OverflowError, TypeError, ArithmeticError):
        return result


if __name__ == "__main__":
    import json
    # Safe empty-state CLI; no input file / env / credentials are read.
    print(json.dumps(inspect_stress(None), sort_keys=True))
