# Gold Ultimate supplemental research diagnostics — November 15, 2026

**Scope:** review/v2-portable-tests-20261109 only. Pure offline module
`coordinator/ultimate_research_extensions.js` integrated into the
existing `/api/v3/ultimate/r2` response and the same mobile research
panel. It is ADDITIVE and does not change the SHA-pinned V2 engine
`coordinator/ultimate_v2.js`, strategy calculations, default
`researchCandidate`, paper-order eligibility, broker routes, or production.

Completed:
1. **Market regime:** classified from 21 structurally valid, **closed,
   consecutive** candles per M15/H1/H4. Efficiency ratio, cross-frame
   directional alignment and simple volatility shock are explicitly
   *uncalibrated heuristic observations*, not predictions.
2. **Economic surprise:** synthetic-only, causally available
   actual/consensus/previous for CPI/PPI/NFP/PCE/FOMC/GDP/ISM.
   Pure numeric surprise, no general rule claiming gold rises/falls.
   Future release, missing consensus or unlicensed feed refused.
3. **Cross-asset conflict:** derived only from existing independently
   evaluated DXY, GC and exchange-trade order-flow layer results.
   Reject stale/mismatched observations and differing GC contracts.
   Opposing evidence returns advisory `NONE`; base engine remains
   `WAIT` throughout.
4. **Daily TIPS real yield:** synthetic DFII10 (official 10-year
   inflation-indexed constant-maturity reference) requires a matching
   already-accepted nominal DGS10 observation *same day and as-of
   availability*. Computes nominal less real as indicative breakeven.
   No official TIPS fetch added; the daily series is **not** intraday.
5. **Outcome quality:** strictly labelled synthetic,
   chronologically completed post-frozen-holdout trades report net
   R, max drawdown, win rate, and profit factor. Synthetic geometry
   cannot prove real OOS calibration, commissions, profitability
   or a meaningful trading win probability.

Inputs without explicitly labelled synthetic researchReview evidence
fail closed with precise blocking reasons. Existing 7-layer feed
contracts and 9-layer provider readiness remain separate; do not
mistake the optional research additions for licensed live sources.

**All results**: `signal: WAIT`, `executable: false`,
`researchEligible: false`, `paperOrdersAllowed: false`,
`predictedWinRate: null`, no vendor requests, credentials,
broker orders, subscriptions, Render deployment or actual market data.

Further prerequisites: confirm Massive BBO history/live entitlement,
GC exchange rights and live depth, licensed DXY and consensus feed,
official DFII10 daily release timing, independent forward holdout and
verified broker spread/slippage before new evidence can be admitted.
