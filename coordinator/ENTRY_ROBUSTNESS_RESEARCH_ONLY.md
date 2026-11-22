# Entry robustness stress — frozen V3 research extension

This extension is **diagnostics only** on branch `review/v2-portable-tests-20261109`.
It does not alter the frozen V3 market-structure logic, quality-shadow veto,
trade-plan pricing, paper-admission gates, live application, or execution.

## What this adds

`ultimate_entry_robustness.js` consumes the already-observed closed
M15/H1/H4 frames, V3 BUY/SELL research candidate, existing proposed
entry/stop/target, and **assumed** spread/slippage/commission figures.
It emits a separate quality report without producing trading decisions.

- Checks each timeframe contains aligned, closed, fresh bars at the decision
  time; rejects missing/invalid inputs instead of using an open candle.
- Uses 14 **prior closed** M15 true ranges to estimate ATR, keeping the last
  decision bar out of the ATR denominator.
- Describes a large opposing wick (>=45% last M15 range) and a proposed
  entry too distant (>0.75 prior ATR) from last observed closed M15 price.
  These are **exploratory hypotheses**, not empirically optimized thresholds.
- Calculates round-trip net reward:risk under the input cost estimate,
  and 1.5x and 2x spread-plus-slippage shocks (commission unchanged).
  Marks fragility if any tested net R:R <1.5 or costs erase gross reward.
- For a simple single full TP/full SL binary outcome, computes the
  **arithmetic** break-even win rate required at each stress level. This is
  NOT a forecast of future win rate. It ignores partial TP1/TP2 exits,
  gaps, fills, slippage tails, stop-first ambiguity, latency and outages.

The `postCostRiskQuality` names describe **only the arithmetic stress
scenario**. In particular, `PASSED_SYNTHETIC_STRESS_ASSUMPTIONS_ONLY` does
not certify data provenance, source rights, broker execution, predictive
accuracy or profitability.

## Why this is safe

A fail-closed report retains `signal:WAIT`, `executable:false`,
`paperOrdersAllowed:false`, `liveOrdersAllowed:false`,
`confidencePercent:null`, and `empiricalWinProbability:null`.
Even a synthetic passing scenario does not enable any trades. The four-stage
viewer exposes only diagnostic ratios and warning labels, not extra voting
rights. There are no network calls, orders or subscriptions.

## Validation before any signal-quality claim

Compare the frozen baseline and the unchanged candidate set with/without
this filter on an **untouched prospective** holdout. Predeclare rules and
failure modes; use real, independently permitted broker-side Bid/Ask,
round-trip spread, slip, lot-size/commission and session data. Measure net
expectancy R, drawdown, missed signals, false suppression, regime variance
and the number of admitted trades. Check that any performance improvement
is stable across time periods and adequate sample sizes, then shadow-test
with paper-only outcomes. **No improvement in win percentage or guarantee
has been measured by the synthetic tests.**

Offline unit test:
`node coordinator/test_ultimate_entry_robustness.js`.
The GitHub workflow `ultimate-signal-quality-offline-review.yml` also runs
the V3 report/four-stage regression and unchanged strategy safety tests.
