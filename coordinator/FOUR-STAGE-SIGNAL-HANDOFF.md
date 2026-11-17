# Gold Precision Pro Ultimate — four-stage signal readiness (review only)

**Repository branch:** `review/v2-portable-tests-20261109` only.
**Trading:** WAIT / executable=false. No payment, subscriptions, broker orders, live-admissible BUY/SELL, or production changes.

## Implementation added

1. **Market data geometry:** the bounded BiQuote 24h observer now counts separately
   `UNCLASSIFIED_M15_COVERAGE_GAP`, `OHLC_PRICE_DISAGREEMENT`,
   `OTHER_SOURCE_SHAPE_FAILURE`, and passes, instead of treating every
   HTTP-success/structural-failure as wrong prices. Counters are metadata only.
   The 24h capture remains bounded and has no extra provider requests.
2. **Signal/entry mechanics:** `coordinator/ultimate_four_stage_review.js`
   composes the existing frozen V3 engine and independent signal-quality/shadow
   inspectors without changing strategy. On synthetic fixture data only, it
   can show a hypothetical direction with Entry, Stop Loss, TP1 (1R),
   TP2 (1.5R), and TP3 (frozen V3 plan target), *all explicitly non-executable*.
   It does not emit a top-level BUY or SELL and is not a paper admission signal.
3. **Confirmation layers:** the review reports DXY, US02Y, US10Y, GC,
   economic calendar, headlines, and licensed trade-side Order Flow as
   provisional model inputs or unavailable. They are never independently
   attested merely because a test fixture includes them. Binance XAUUSDT
   cannot substitute for COMEX GC or licensed spot XAUUSD.
4. **Prospective and paper:** `test_ultimate_four_stage_review.js` and
   `test_ultimate_four_stage_paper.py` verify no lookahead, stale/missing
   frames and feeds, unclassified calendar gaps, risk and licence separation,
   hypothetical stop/target geometry, and no automatic paper positions
   from even a positive synthetic BUY fixture. Existing historical walk-forward
   and paper simulators are unchanged; these tests are **not profitability**.

Run locally with no network:

```sh
node coordinator/test_ultimate_four_stage_review.js
python3 -m unittest -v coordinator/test_ultimate_four_stage_paper.py
```

## The actual blockers before usable trading signals

- **Data licence and archive:** verify independent underlying MT5 broker data
  rights; confirm source session/calendar, XAUUSD symbol convention, OHLC
  consistency on actual observations, quote freshness, and protected storage.
  Stage a private 24h capture at 2026-11-18T00:00:00Z only if approved and
  the previous 24h observation has completed. No newly stored candles have
  been attested by these offline tests.
- **Enough unseen history:** retain minimum closed M15/H1/H4 observations,
  avoid fabricating missing session candles, and validate bid/ask and broker
  spread/slippage commissions on historical execution. A 24h smoke capture
  is not months of untouched out-of-sample data.
- **Source rights/freshness:** independent entitlement and as-of timestamps
  for DXY, GC, historical trade-side Order Flow, news/calendar; US02Y/US10Y
  official daily data cannot stand in for live yields. Do not assume
  synthetic/fixture evidence or an unsupported source as live confirmation.
- **Statistical acceptance:** run preregistered prospective independent
  paper tests against frozen V3 and V2 baselines; measure after-cost
  expectancy, drawdown, regime sensitivity, stop-first execution,
  missed candles and data outages. Do not enable or promise trades from an
  attractive in-sample win rate. Separate owner approval remains necessary
  before *any* real broker trade.

The offline preview remains `WAIT` at the public signal boundary and
`paperOrdersAllowed=false` even when a nested synthetic plan has BUY/SELL.
