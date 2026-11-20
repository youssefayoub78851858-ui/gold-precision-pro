"""Offline five-stage pre-subscription inventory. Never reads secrets or contacts vendors."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from eodhd_bootstrap_preflight import bootstrap_plan
from capital_demo_historical_batch_plan import plan_demo_closed_history

ROOT = Path(__file__).resolve().parent.parent
CHECKS = {
    "review_runtime": [
        ("coordinator/entrypoint.py", ["CUTOVER_MODE", "standby", "BROKER_TOKEN"]),
        ("coordinator/Dockerfile", ["entrypoint.py", "private_eodhd_worker.py"]),
        ("coordinator/entrypoint.py", ["launch_review_worker", "stop_review_worker"]),
        ("coordinator/eodhd_private_readiness.py", ["signal", "WAIT", "executable"]),
        ("coordinator/test_container_standby.py", ["--network=none"]),
        ("coordinator/private_mobile_dashboard.html", ["/api/v3/monitor/status", 'type="password"', "WAIT"]),
        ("coordinator/test_private_mobile_dashboard.py", ["test_no_public_quote_or_trading_surface"]),
        ("coordinator/entrypoint.py", ["/api/v3/monitor/dashboard", "monitor_ready=authenticated"]),
    ],
    "gold_prices": [
        # SELECTED primary: Capital.com Demo. Legacy EODHD is still
        # independently audited below, but must not be marketed as primary.
        ("coordinator/capital_demo_private_get_boundary.py",
         ["CAPITAL_DEMO_PRIVATE_PRICE_GET_ENABLED",
          "CAPITAL_DEMO_PRIVATE_RIGHTS_DOCUMENTED",
          "PRIVATE_DEMO_GET_STANDBY", "orderRouteSupported"]),
        ("coordinator/capital_demo_https_transport.py",
         ["NoRedirect", "HTTPSHandler", "PRIVATE_DEMO_TRANSPORT_NOT_APPROVED",
          "DEMO_PRICE_HOST_AND_ROUTE_REQUIRED", "MAX_BYTES"]),
        ("coordinator/capital_demo_historical_batch_plan.py",
         ["plan_demo_closed_history", "MAX_ROWS_PER_CALL", "INERT_PLAN_ONLY"]),
        ("coordinator/capital_demo_offline_batch_audit.py",
         ["audit_disabled_history_pages", "BROKER_EPIC_MISMATCH", "BROKER_RESOLUTION_MISMATCH"]),
        ("coordinator/capital_demo_receipt_preflight.py",
         ["inspect_receipts", "UNATTESTED_SANITIZED_CAPITAL_DEMO_RECEIPTS"]),
        ("coordinator/capital_demo_historical_receipt_link.py",
         ["inspect_link", "RECEIPT_BARS_DIFFER_FROM_HISTORICAL_BARS"]),
        ("coordinator/test_capital_demo_private_end_to_end.py",
         ["test_private_only_synthetic_flow_without_orders",
          "test_default_never_fetches_or_delivers_even_with_tokens"]),
        ("coordinator/test_capital_demo_https_transport.py",
         ["test_inert_without_both_flags_and_independent_operator_approval"]),
        ("coordinator/private_mobile_dashboard.html",
         ["مصدر الذهب المختار: Capital.com Demo", "WAIT"]),
        ("coordinator/CAPITAL-DEMO-PRIVATE-HANDOFF.md",
         ["Capital.com Demo", "GET /api/v1/prices/{epic}"]),
    ],
    "context_and_news": [
        ("coordinator/h15_official_rss.js", ["DGS2", "DGS10"]),
        ("coordinator/official_macro_review.js", ["FED_URL", "BLS_URL"]),
        ("coordinator/ultimate_v2_contracts.js", ["orderFlow", "headlines", "calendar", "DXY", "GC"]),
        ("coordinator/ultimate_news_impact.js", ["GEOPOLITICAL_RISK", "signal"]),
        ("coordinator/official_context_stage.js", ["geopoliticalWorldNewsCoverage:false", "completeUsdCalendarCoverage:false", "collectOfficialContext", "inventoryForOfficialContext"]),
        ("coordinator/official_source_inventory.js", ["ICE", "DXY", "GC_ORDER_FLOW", "NOT_SEPARATELY_VERIFIED", "WAIT"]),
        ("coordinator/test_official_source_inventory.js", ["proveBlocked", "UNEXPECTED_NETWORK"]),
        ("coordinator/test_official_context_stage.js", ["assertSafe", "OFFICIAL_CONTEXT_CONTRACT_INVALID"]),
        ("server.js", ["/api/v3/ultimate/official-context-stage", "OFFICIAL_CONTEXT_NETWORK_APPROVED"]),
        ("ultimate.html", ["official-context-check", "official-context-status"]),
    ],
    "paper_and_monitoring": [
        ("coordinator/ultimate_paper.py", ["PaperAccount", "executable"]),
        ("coordinator/paper_admission_gate.py", ["assess_paper_gate", "PAPER_LIVE_ACTIVATION_NOT_APPROVED", "RISK_AND_BROKER_COSTS_NOT_VERIFIED"]),
        ("coordinator/paper_cost_preflight.py", ["synthetic_scenario_cost", "cost_readiness", "BROKER_CONTRACT_AND_LOT_SPEC_UNVERIFIED"]),
        ("coordinator/test_paper_cost_preflight.py", ["test_cost_arithmetic_and_risk_ceiling_is_synthetic"]),
        ("coordinator/test_paper_admission_gate.py", ["test_forged_and_synthetic_cannot_arm_paper"]),
        ("coordinator/research_monitor_runner.py", ["run_continuously", "WAIT"]),
        ("coordinator/research_notification.py", ["executable"]),
        ("coordinator/private_review_watchdog.py", ["run_until_stopped", "observe_once", "AUDIT_STALE", "WAIT"]),
        ("coordinator/private_feed_recovery.py", ["observe_recovery", "OBSERVATION_REPEATED_UNVERIFIED", "paperOrdersAllowed"]),
        ("coordinator/test_private_feed_recovery.py", ["test_loss_then_three_separate_observations_then_interrupt"]),
        ("coordinator/test_private_review_watchdog.py", ["test_outage_is_recorded_once_and_survives_restart"]),
    ],
    "mt5_demo": [
        ("mt5/Experts/GoldPrecisionReadOnlyExport.mq5", ["ACCOUNT_TRADE_MODE_DEMO"]),
        ("coordinator/import_mt5_readonly.py", ["CLOCK_BASIS_UNVERIFIED"]),
        ("coordinator/mt5_clock_diagnostic.py", ["CLOCK_BASIS_UNVERIFIED"]),
    ],
}
STAGES = [
    ("review_runtime", "private review runtime",
     "AWAITING_APPROVED_PRIVATE_REVIEW_DEPLOY",
     "Private Render deploy needs separate approval and authenticated HTTP checks"),
    ("gold_prices", "selected Capital.com Demo XAUUSD private price feed",
     "AWAITING_ENTITLEMENT_AND_REAL_DATA_TEST",
     "Capital.com Demo account eligibility and private cloud rights, restricted gateway, real bid/ask timestamps, broker sessions and full M15/H1/H4 history must be independently verified"),
    ("context_and_news", "DXY, US yields, GC order flow and comprehensive news",
     "AWAITING_AUTHORIZED_DATA_SOURCES",
     "Verify official free sources and licensed live GC/DXY/news coverage before admitting signals"),
    ("paper_and_monitoring", "continuous research and paper trading",
     "AWAITING_LIVE_VALIDATED_PIPELINE",
     "Connect verified sources, costs, private ledger, watchdog and alert transport"),
    ("mt5_demo", "MT5 Demo clock and orders",
     "AWAITING_WINDOWS_DEMO_AND_CLOCK_EVIDENCE",
     "Compile EA on Windows, capture Demo UTC/DST evidence and verify broker rights first"),
]
def _selected_capital_demo_plan() -> dict:
    """Count-only offline forecast of required Demo history calls, not an API call."""
    planned = plan_demo_closed_history(
        "TEST.GOLD.EPIC", "2026-11-08T00:00:00Z",
        "2026-11-18T00:00:00Z", "2026-11-20T12:00:00Z")
    return {
        "selectedProvider": "CAPITAL_COM_DEMO",
        "status": "UNCONNECTED_RESTRICTED_STANDBY",
        "signal": "WAIT", "executable": False,
        "researchEligible": False, "paperOrdersAllowed": False,
        "realTradingAuthorized": False, "rightsVerified": False,
        "brokerAccountVerified": False, "readOnlyApiKeyGranted": False,
        "independentBrokerSessionVerified": False,
        "pointInTimeBidAskVerified": False,
        "credentialsUsed": False, "providerRequestsMade": 0,
        "liveMarketDataAvailable": False,
        "offlineHistoricalBlueprint": {
            "status": planned["status"],
            "plannedGETRequests": planned.get("requestCount", 0),
            "expectedUTCGridClosedSlots": planned.get("expectedClosedBarCounts", {}),
            "providerCallsSent": 0,
            "actualSessionOrMarketDataProven": False,
        },
        "remainingExternalConditions": [
            "CAPITAL_PRIVATE_RENDER_RESEARCH_RIGHTS_AND_ELIGIBILITY_IN_LEBANON",
            "DEMO_ACCOUNT_VERIFICATION_AND_ISOLATED_TRADING_CAPABLE_API_SESSION",
            "INDEPENDENT_BROKER_M15_H1_H4_BID_ASK_SESSION_AND_FIRST_SEEN_PARITY",
            "GC_DXY_NEWS_SYNCHRONIZED_LICENSED_COVERAGE",
            "BROKER_SPREAD_COMMISSION_SLIPPAGE_AND_UNTOUCHED_PAPER_HOLDOUT",
        ],
    }


def build_report(root: Path = ROOT) -> dict:
    root = Path(root)
    checks = {}
    for name, requirements in CHECKS.items():
        missing = []
        for path, guards in requirements:
            try:
                body = (root / path).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                missing.append(path + ":MISSING_OR_UNREADABLE")
                continue
            for guard in guards:
                if guard not in body:
                    missing.append(path + ":MISSING_GUARD:" + guard)
        checks[name] = missing
    stages = [
        {"id": name, "title": title,
         "status": state if not checks[name] else "CODE_PREFLIGHT_FAILED",
         "staticCodeCheck": "PRESENT" if not checks[name] else "BLOCKED",
         "blockingCodeChecks": checks[name],
         "externalGate": action}
        for name, title, state, action in STAGES
    ]
    return {
        "reportVersion": 1,
        "mode": "OFFLINE_PRE_SUBSCRIPTION_ONLY",
        "networkCalls": 0, "secretReads": 0, "payments": 0,
        "liveDataValidated": False, "liveResearchReady": False,
        "paperTradingLiveReady": False, "mt5DemoExecutionReady": False,
        "liveTradingAuthorized": False, "sourceLicensesVerified": False,
        "signal": "WAIT", "executable": False,
        "preSubscriptionStaticChecksPassed": not any(checks.values()),
        "selectedGoldProvider": "CAPITAL_COM_DEMO",
        "selectedCapitalDemoReadiness": _selected_capital_demo_plan(),
        "legacyEodhdAlternativeNotSelected": True,
        "eodhdFirstDayBootstrapPlan": bootstrap_plan(),
        "warning": "Code presence and passing offline tests do not prove live entitlements, deployment, execution readiness or profit",
        "stages": stages,
        "mobileFlow": {
            "free": "GitHub Actions > V2 offline unit tests > Run workflow on review branch",
            "deploy": "Approve private Render review deployment separately; production untouched",
            "vendor": "Capital.com Demo private rights, Lebanon eligibility and account verification remain external blockers; no subscription approved",
            "paper": "Validate live market evidence, broker costs and monitoring before paper trial",
            "mt5": "Windows Demo capture and clock verification required before execution tests",
        },
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if not report["preSubscriptionStaticChecksPassed"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
