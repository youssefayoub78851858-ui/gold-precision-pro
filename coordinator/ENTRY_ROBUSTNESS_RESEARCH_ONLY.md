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

## Actual repository BID-only September–October coverage (2026-11-22)

A separate, deterministic offline inspector
`ultimate_entry_recorded_coverage.js` verifies the SHA-256 hashes from
`research/recorded/manifest.json` and checks M15/H1/H4 OHLC chronology.
It uses only these two previously researched **Dukascopy-derived BID**
files; it does not download anything or access the private vault.

| Descriptive quantity | September | October | Total |
| --- | ---: | ---: | ---: |
| Closed M15 bars in file | 2,448 | 2,436 | 4,884 |
| M15 windows with 16 contiguous candles and positive prior ATR | 2,076 | 2,065 | 4,141 |
| Above with non-flat latest M15 | 1,994 | 1,997 | 3,991 |
| Above with recent closed H1/H4 and locally matching M15 BID OHLC | 1,978 | 1,981 | 3,959 |
| Zero-range M15 bars in full file | 434 | 420 | 854 |

These are **overlapping historical observation windows, not trades or
predictions**. Local higher-timeframe parity is unsurprising when H1/H4
were built from the same M15 BID history; it is not independent broker
verification. Neither period is untouched prospective holdout data.
No original V3 candidate/fill universe, independent ASK side, broker session
calendar, actual execution costs, or authorized quote licence was proven.
**Baseline and filtered win rates, net R, and performance improvement remain
unknown (null), and all trade eligibility remains WAIT.**

The stricter entry-robustness module now fails closed if its last 16 M15
candles, or latest two H1/H4 candles, bridge an unverified timestamp gap,
or if the decision M15 candle has zero range. Those checks deliberately
exclude unverifiable segments; passing them does not guarantee a real
market tick, prove data provenance, or improve trade success probability.

To reproduce in GitHub CI (offline, no private prices):
`node coordinator/test_ultimate_entry_recorded_coverage.js` and
`node coordinator/ultimate_entry_recorded_coverage.js`.

## Frozen V2 recorded shadow comparison (November 22, 2026)

The new `ultimate_entry_v2_shadow_compare.js` generated **frozen V2**
research candidates using the archived BID M15/H1/H4 observations
from September and October 2026. The exact V2 candidate list is kept
unchanged; the independent entry-robustness diagnostic only selects
an offline shadow subset. It then runs the same existing V2 backtester
twice to illustrate what happens with overlapping trades. This is **not
a V3 Ultimate comparison**, not an independent holdout, and not actual
broker execution. No trading or provider contact took place.

For illustration only: spread=0.40 XAUUSD price units, slippage=0.10
price units, commission=7 per lot / value-per-point=100, all
assumed, not observed. Results use modeled full-TP/full-SL outcomes,
stop-first ambiguous candle resolution and a portfolio path that can
change when earlier signals are excluded.

| Development month | V2 candidates | Shadow kept | Baseline modeled win rate | Filtered-path modeled win rate | Baseline modeled net R | Filtered-path modeled net R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| September | 257 | 101 | 26.67% (8/30) | 31.03% (9/29) | −7.40R | −3.47R |
| October | 273 | 137 | 32.14% (9/28) | 25.00% (6/24) | −2.75R | −7.38R |

Doubling the **assumed** spread and slippage produced:
September −8.75R baseline versus −4.78R filtered path;
October −4.25R baseline versus −8.57R filtered path.

A separate `sameBaselineClosedTradeSubset` keeps identical
baseline-filled outcomes for accepted original candidates, while
`shadowFilterPath` is a distinct overlap-affected simulation. Neither
establishes the causal benefit of the new filter. These recorded
months have already been used during development.

**Decision: DO NOT PROMOTE THIS FILTER TO TRADE ADMISSION.** The
modeled difference reversed by month; both filtered months have
negative modeled net R. The comparison now emits an explicit
`comparisonPromotionGate` with
`shadowFilterAdoptionApproved:false` and reason codes. Its value
does not change the frozen V2 engine or V3; `WAIT` remains.

Only a preregistered independent prospective test using permitted
full BID/ASK prices, time-aligned broker sessions and actual costs
can demonstrate that a filter improves profitability. Even a better
historical win rate does not guarantee future returns.

The offline comparison is run in the signal-quality GitHub workflow:
`node coordinator/test_ultimate_entry_v2_shadow_compare.js`
and `node coordinator/ultimate_entry_v2_shadow_compare.js`.

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
