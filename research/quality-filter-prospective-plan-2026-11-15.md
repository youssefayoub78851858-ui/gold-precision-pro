# Prospective Gold Signal-Quality Audit — REVIEW ONLY (2026-11-15)

## Why
A new technical indicator or heuristic **cannot be called profitable** until a
predeclared, chronology-preserving evaluation on independently sourced market
data has shown net improvement after real trading costs. This audit DOES NOT
alter the frozen V3 engine, BUY/SELL/WAIT eligibility, paper admission, or orders.

## Files
- `coordinator/ultimate_signal_quality.js`: pure, closed-candle diagnostic only
- `coordinator/ultimate_signal_quality_report.js`: isolated wrapper around the frozen V3
- `coordinator/test_ultimate_signal_quality.js`: offline adversarial regression
- `.github/workflows/ultimate-signal-quality-offline-review.yml`: automated offline tests

## Fixed exploratory rules (declared before outcomes)
- M15 close-path efficiency over 20 bars: <= 0.25 CHOPPY; >= 0.60 DIRECTIONAL; else MIXED.
- Last true range >= 2.5 times preceding 14-period ATR: SINGLE_CANDLE_VOLATILITY_SHOCK.
- Net reward/risk estimate < 1.5: COST_ADJUSTED_REWARD_RISK_LOW.
  This is estimated from known entry/stop/target, spread, slippage and commission per lot / value per point; not a quote/fill guarantee.
- No broker/calendar-verified coverage for a timestamp gap: flag a calendar audit requirement; do not invent missing candles.
- Calendar/news missing or high-impact event window: warn rather than falsely assert a verified event feed.
- All outputs: signal WAIT, executable false, paperOrdersAllowed false, probability null. A score is NOT produced.

These thresholds are not optimized or claimed to predict profit; do not modify them
using the same months used for final testing. They are hypotheses.

## Required next evidence — not yet available
1. Independently licensed, timestamped, real XAUUSD M15/H1/H4 with provenance,
   broker session calendar, bid/ask convention, variable spread, and fill assumptions.
2. Chronological training, validation, untouched holdout and prospective paper periods.
   Never fit with future candles or use future headline availability.
3. Compare the *same* frozen research candidate set with/without each warning
   as a selection rule. Report signal count, skipped opportunities, net expectancy R,
   profit factor, max drawdown, gross and net P&L, and costs; include adverse scenarios.
4. Segment outcomes by directional/choppy/mixed regime and news/session hours,
   and disclose low sample sizes and temporal dependence. Do not claim statistical
   reliability from a few selected successes or historical backtest alone.
5. Keep any execution/paper activation blocked until separately authorized by
   the operator with licensed feed, risk and source rights verified.

## No actions performed
No provider requests, credentials, external storage, publication, Render deployment,
real trading or paper orders are initiated by these files.
