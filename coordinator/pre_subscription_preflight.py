"""Offline five-stage pre-subscription inventory. Never reads secrets or contacts vendors."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

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
        ("coordinator/eodhd_ws_bridge.js", ["EODHD_CONNECT_APPROVED", "EODHD_RIGHTS_APPROVED", "EODHD_API_TOKEN", "XAUUSD"]),
        ("coordinator/private_eodhd_worker.py", ["PRIVATE_EODHD_REVIEW_WORKER_ENABLED", "EODHD_CONNECT_APPROVED", "EODHD_RIGHTS_APPROVED", "EODHD_API_TOKEN", "standby"]),
        ("coordinator/xauusd_feed_gate.py", ["SourcePolicy", "intake_payload", "expectedOpenTimes"]),
        ("coordinator/xauusd_research_pipeline.py", ["run_research_pipeline", "researchEligible"]),
        ("coordinator/eodhd_research_bridge.py", ["run_research_pipeline", "BID_ASK_AGGREGATE_MISMATCH", "INDEPENDENT_SESSION_HISTORY_OR_CLOCK_EVIDENCE_MISSING"]),
        ("coordinator/test_eodhd_research_bridge.py", ["test_mock_cannot_claim_live_research_without_50_h4_bars"]),
    ],
    "context_and_news": [
        ("coordinator/h15_official_rss.js", ["DGS2", "DGS10"]),
        ("coordinator/official_macro_review.js", ["FED_URL", "BLS_URL"]),
        ("coordinator/ultimate_v2_contracts.js", ["orderFlow", "headlines", "calendar", "DXY", "GC"]),
        ("coordinator/ultimate_news_impact.js", ["GEOPOLITICAL_RISK", "signal"]),
        ("coordinator/official_context_stage.js", ["geopoliticalWorldNewsCoverage:false", "completeUsdCalendarCoverage:false", "collectOfficialContext"]),
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
    ("gold_prices", "licensed XAUUSD current-session feed",
     "AWAITING_ENTITLEMENT_AND_REAL_DATA_TEST",
     "Plan, license, private API token, live WebSocket and full closed-bar history must be verified"),
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
        "warning": "Code presence and passing offline tests do not prove live entitlements, deployment, execution readiness or profit",
        "stages": stages,
        "mobileFlow": {
            "free": "GitHub Actions > V2 offline unit tests > Run workflow on review branch",
            "deploy": "Approve private Render review deployment separately; production untouched",
            "vendor": "Subscription and private token configuration require user action",
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
