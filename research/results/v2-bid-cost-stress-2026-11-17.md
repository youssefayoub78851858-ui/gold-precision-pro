# XAU/USD frozen V2 — archived BID-only cost stress (2026-11-17)

**Recorded CI evidence:** https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/44062027963  
**Audit code:** \`coordinator/archived_bid_cost_sensitivity.js\`  
**Only branch modified:** \`review/v2-portable-tests-20261109\`

## Result on existing September / October 2026 DEVELOPMENT archives

This is the **unchanged frozen V2 EMA/RSI/ATR strategy**, not V3 Ultimate.
For each month it uses the existing SHA-256 checked BID-only XAU/USD bars and
re-runs the same historical trade geometry at fixed **hypothetical round-trip
price-friction deductions** of 0.40, 0.80, and 1.20 USD per troy ounce.
This is *not* a quote of actual broker spreads or a measurement of ASK fills.

| Archived month | M15 BID candles | Closed trades | Net profitable | Closed-trade win rate | Net R @0.40 | Net R @0.80 | Net R @1.20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| September | 2,448 | 30 | 8 | 26.67% | -6.946172 | -8.020157 | -9.094142 |
| October | 2,436 | 28 | 9 | 32.14% | -2.235326 | -3.441026 | -4.646727 |
| **Sum of separate months** | **4,884** | **58** | **17** | **29.31%** | **-9.181497** | **-11.461183** | **-13.740869** |

**Gross sum before friction** = -6.901811 R. There were 530 raw
directional *signal events* (257 September, 273 October), but only 58
closed simulated trades due to no-overlap handling. One position was open
at the end of the September sample and excluded from closed-trade metrics.
At 0.40, September closed-trade max drawdown is 11.807759 R; October's
is 10.121763 R. **No combined portfolio drawdown** or seamless
September-to-October trade roll-forward was calculated.

Integrity-verified local recording hashes:
- \`2026-09-bid.json\`: SHA-256 \`f26f05c50b2431f759161cc3b0c52fd531a2f3ffbd03e9033c3ce4e2f1509af4\`
- \`2026-10-bid.json\`: SHA-256 \`2ce22184be6cdadd16e24b79945c4cb5a02974cb3f0b654dcc6a759d1878f4e\`

## What this result DOES NOT establish

- **Not a new independent holdout:** September and October recordings have
  already been used during development. Do not optimize on their losses and
  then call an in-sample improvement out-of-sample.
- **Not V3 Ultimate performance:** DXY, US02Y, US10Y, GC, order flow,
  calendar and news were not present as synchronized decision-time inputs
  for this backtest.
- **Not actual after-broker-cost PnL:** Only BID historical candles exist.
  No synchronized ASK data, true spread regime, slippage, commissions,
  execution venue fills, real-money risk or opening/closing fee model exists.
  Friction is a hypothetical fixed *price* deduction to the archived V2
  backtest's normalized R, not a verified account statement.
- Hashes verify consistency of repository artifacts, not independent
  provider authenticity or cloud redistribution rights.
- The runner is offline and sends **zero** provider requests or orders.

**Research decision: WAIT, executable:false, no live or paper orders**.
The negative V2 development baseline means no profitability claim; a fresh,
licensed, synchronized historical BID/ASK series with decision-time
macro/news/GC inputs and a predeclared untouched future holdout are still
required before assessing V3 Ultimate strategy performance.

**Reproduce:** \`node coordinator/test_archived_bid_cost_sensitivity.js\`,
then \`node coordinator/archived_bid_cost_sensitivity.js\`.
