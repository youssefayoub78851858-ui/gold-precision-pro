# Gold Precision Pro Ultimate — Implementation contract (2026-11-10)

Status: research and paper-only. No validated profitable strategy. No live orders.

## Existing verified baseline
- V2 frozen EMA/RSI/ATR is not profitable in Sep/Oct 2026 research backtests.
- Historical M15 data must be validated; H1/H4 should be rebuilt from complete M15 bars.
- Backtest is next-M15-open, stop-first if ambiguous, fixed approximate $0.40 spread; no variable bid/ask, commissions, slippage or latency.
- Do not optimize for win rate alone. Primary measure: positive net expectancy with drawdown limits, across unseen time windows.

## Delivery order (hard gates)
1. **Data/execution integrity**: deterministic OHLC checks, UTC and session-gap checks, broker bid/ask model where data supports it, spread/slippage sensitivity, no-lookahead tests, invariant accounting.
2. **Research engine V3 (isolated)**: market structure on H4/H1/M15, swing points, BOS/CHoCH, liquidity sweeps, FVG, volatility and session context. Emit BUY/SELL/WAIT plus timestamped reason and invalidation. No future-bar inputs.
3. **Independent evidence layers**: DXY, US02Y/US10Y, GC futures, economic calendar and headline event impact; mark each feed as live/delayed/unavailable and WAIT when mandatory feeds are stale. Order Flow/footprint only if licensed real feed exists; never infer true order flow from candle volume.
4. **Validation**: rolling walk-forward train/validation/test, regime segmentation, no cherry-picking, fixed risk, commissions and execution sensitivity, bootstrap confidence intervals, compare V2 and naive benchmarks. Keep untouched holdout months.
5. **Paper mode**: broker-independent signals, bounded position risk, one active trade, kill-switch, daily max loss, audit logs and operator review.
6. **Deployment and execution**: staged Render cutover only after provider-quota handoff guard passes; MT5 real-money execution requires separate explicit approval.

## Safety and cost constraints
- Never modify main, backup-v1, fix-analysis-v2, or existing public Render without explicit approval.
- Develop on review branch; no new subscriptions or secret exposure.
- No claims of 70%/90%/99% guaranteed wins. WIN RATE is diagnostic, not the objective.
- Do not add arbitrary filters just to improve an in-sample month.
- Record data origin, timestamp, bid/ask conventions, and sample coverage for every published result.

## Next engineering milestone
Implement a separate, deterministic V3 market-structure signal module with tests for swing confirmation, BOS/CHoCH, liquidity sweep, FVG and strict no-lookahead. Preserve frozen V2 and compare on real data only after data/execution integrity gate.
