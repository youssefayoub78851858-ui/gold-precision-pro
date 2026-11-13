"""Offline XAU/USD first-day history and licensing readiness, never an API client.

Streaming FX bid/ask ticks cannot backfill historical candles before the
connection starts. EODHD separately documents delayed Forex intraday OHLCV;
its OHLC convention and rights must be independently verified before mixing
that history with BID-based WebSocket M15/H1/H4 observations.
No quotes, subscriptions, credentials, network, orders or live status here.
"""
from __future__ import annotations

import argparse
import json
from eodhd_research_bridge import MIN_WARMUP_BARS

M15_PER_H4 = 16
DOCS_WEBSOCKET = "https://eodhd.com/financial-apis/new-real-time-data-api-websockets"
DOCS_INTRADAY = "https://eodhd.com/financial-apis/intraday-historical-data-api"


def bootstrap_plan(counts=None):
    """A count-only arithmetic diagnostic; cannot certify data provenance."""
    observed = {"M15": 0, "H1": 0, "H4": 0}
    if counts is not None:
        if not isinstance(counts, dict) or set(counts) != set(observed):
            raise ValueError("Exact M15/H1/H4 closed counts required")
        for key, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Non-negative integer closed counts required")
        observed.update(counts)

    minimum = dict(MIN_WARMUP_BARS)
    if minimum != {"M15": 50, "H1": 50, "H4": 50}:
        raise RuntimeError("Unexpected indicator warmup contract")
    missing = {tf: max(0, minimum[tf] - observed[tf]) for tf in minimum}
    enough_counts = all(value == 0 for value in missing.values())
    # 800 M15 bars is only the mathematical minimum: the actual time range
    # may need more due to market closures, partial H4 boundaries and outages.
    minimum_m15_h4 = M15_PER_H4 * minimum["H4"]
    blockers = [
        "EODHD_XAUUSD_CLOUD_ENTITLEMENT_AND_RIGHTS_NOT_VERIFIED",
        "HISTORICAL_FOREX_OHLCV_VS_WEBSOCKET_BID_ASK_EQUIVALENCE_UNVERIFIED",
        "INDEPENDENT_UTC_SESSION_CALENDAR_AND_CLOCK_NOT_VERIFIED",
        "LIVE_FEED_AND_RESTART_CONTINUITY_NOT_TESTED",
        "OTHER_ULTIMATE_LAYERS_AND_BROKER_COSTS_NOT_VERIFIED",
    ]
    if not enough_counts:
        blockers.insert(0, "CLOSED_BAR_WARMUP_COUNTS_BELOW_MINIMUM")
    if observed["M15"] < minimum_m15_h4:
        blockers.insert(1 if not enough_counts else 0,
                        "LESS_THAN_800_CLOSED_M15_SLOTS_FOR_50_H4")

    return {
        "mode": "OFFLINE_XAUUSD_FIRST_DAY_BOOTSTRAP_REVIEW",
        "signal": "WAIT",
        "executable": False,
        "readyForTrading": False,
        "readyForPaper": False,
        "historyReadyForResearch": False,
        "sourceRequestsMade": 0,
        "secretReads": 0,
        "payments": 0,
        "dataSource": "EODHD_XAUUSD_NOT_ACTIVATED",
        "inputCountBasis": "UNVERIFIED_COUNTS_NOT_PROOF_OF_MARKET_HISTORY",
        "minimumClosedBars": minimum,
        "observedClosedBars": observed,
        "missingToMinimum": missing,
        "countMinimumsMet": enough_counts,
        "historyMath": {
            "m15PerH4": M15_PER_H4,
            "minimumClosedM15For50CompleteH4": minimum_m15_h4,
            "minimumContinuousHoursAtFullMarketCoverage": minimum_m15_h4 * 15 // 60,
            "800M15SufficientWithoutAlignedCompleteGroups": False,
            "marketClosuresOrTickOutagesCanRequireMoreHistory": True,
        },
        "sourceCompatibility": {
            "streamType": "WEBSOCKET_FOREX_BID_ASK_TICKS",
            "historicalRestType": "SEPARATE_DELAYED_INTRADAY_OHLCV",
            "websocketDocumentation": DOCS_WEBSOCKET,
            "historicalDocumentation": DOCS_INTRADAY,
            "historicalXauUsdSubscriptionVerified": False,
            "bidAskHistoricalConventionVerified": False,
            "licenseAllowsCloudUseVerified": False,
            "mayMergeHistoricalAndStreamBars": False,
            "actualHistoricalDataDownloaded": False,
        },
        "blockingReasons": blockers,
        "nextRequiredEvidence": [
            "Written XAUUSD.FOREX intraday-history entitlement and Render research rights",
            "Official bar-price convention (bid/ask/mid) and same-feed parity evidence",
            "Licensed, independently dated historical sample with 50 complete H4 groups",
            "Verified UTC market session calendar and gap/restart comparison",
        ],
        "warning": ("Count arithmetic and provider documentation do not prove paid "
                    "access, historical quality, real-time signal eligibility or profit"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = json.dumps(bootstrap_plan(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        from pathlib import Path
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
