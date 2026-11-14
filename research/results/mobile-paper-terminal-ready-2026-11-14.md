# Gold Precision Pro Ultimate paper terminal — review only (2026-11-14)

Actual mobile HTML/UI implemented at /paper-terminal, served ONLY by DEMO_MODE
review service (not production). The CI tests do not deploy it; Render's
autoDeploy is disabled. User approval is required before any Render deploy.

Features:
- Responsive Android-ready navy/gold candlestick chart on CLOSED M15, H1,
  H4 Bid/Ask candles, sourced from local uploaded JSON or explicitly
  labeled deterministic SYNTHETIC_TEST_ONLY fixture.
- Offline click-by-click candle replay, manual BUY/SELL paper opening and
  closing, configurable SL and three TP levels (TP3 automatic), conservative
  stop-first assumption when stop and target both touched in one M15 bar.
- 0.01 lots, XAU convention 100 USD per point per full lot, model
  spread from Bid/Ask, $0.05 slippage per side, $7/lot round-trip commission.
  Paper risk <=0.5% per position and 2% daily loss; one open at a time.
- Local device session/journal; export JSON, results, win%, maximum realized
  equity drawdown and profit factor. All results are explicitly hypothetical.
- No real-time feed, no broker API, no market-data API and no real orders.
  No price is presented as live; signal WAIT and entry/SL/TP from actual
  research engine remain unavailable. User-manual paper fields are not advice.

POST /api/v3/paper/inspect is a synthetic-only OFFLINE research review:
it normalizes a strictly closed M15 Bid/Ask prefix, builds H1/H4, and
reuses the existing Ultimate V3 r2 engine and market-structure module.
It reports BOS/CHoCH/sweeps/FVG, technical indicators and missing
macro/GC/news/order-flow gates, never a live BUY or SELL recommendation.
It rejects recorded unlicensed data and client claims to be authorized.
The endpoint accepts no secrets, makes zero provider calls, and cannot
publish live prices or place any trading orders. The local session never
posts an uploaded recorded file to the research endpoint.

Offline original Python SQLite paper and V2 frozen algorithm remain
unchanged. The new UI is a transparent browser-only manual paper lab,
not a substitute for execution integration or a validated profitable strategy.
Existing recorded Sep/Oct backtest and walk-forward data remain preserved
without cherry-picking; no prospective claim has been made.
Blocked work: written feed/cloud rights, broker trading-disabled credentials,
actual XAUUSD Bid/Ask and session clock proof, DXY/GC/news/order-flow
entitlements, monitored real-data paper trading. FXCM is not connected.

Developer acceptance: node test_paper_terminal_core.js;
node coordinator/test_paper_terminal_inspect.js;
existing coordinator/test_ultimate_http.py includes demo-only routes.
