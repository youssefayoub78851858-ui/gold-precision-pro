# Ultimate offline research batch

Review branch only: `review/v2-portable-tests-20261109`.
Base: `1526b317eaaa34d3bbd00df6c7838188f24c97e7`.

## Run without providers

```sh
DEMO_MODE=standby PORT=3000 node server.js
# Open http://localhost:3000/ultimate and upload coordinator/fixtures/ultimate-synthetic.json
node coordinator/v3_ultimate.js coordinator/fixtures/ultimate-synthetic.json
python coordinator/ultimate_replay.py coordinator/fixtures/ultimate-synthetic.json --database /tmp/ultimate-audit.sqlite3
```

The UI makes no automatic requests. POST `/api/v3/ultimate` accepts at most 1 MiB of evidence JSON. GET `/ultimate` serves the offline file-upload interface. CLI and HTTP share the same deterministic evaluator. The original V2 and V3 research routes remain separate.

## Implemented in this batch

- Closed-bar M15/H1/H4 technical alignment, existing confirmed pivots, BOS, sweeps and FVG are reused. Adds 14-bar true-range volatility, spread gating and fixed UTC session context. CHoCH fields are **heuristics based on prior range bias**, not a fully validated structural trend state machine.
- Independent DXY, US02Y, US10Y and GC reference direction; explicit synthetic/recorded provenance, observation timestamp, and five-minute freshness. DXY and yields are inverse directional research evidence; GC agrees with gold. These are hypotheses, not calibrated predictive models.
- Calendar and headlines accept supplied classified events, require coverage of the entire ±30-minute window, and veto high-impact events. No news collection, language sentiment model, or external API is connected.
- Trade-side buy/sell volume delta requires declared trade provenance and licensing. Candle volume cannot substitute for order flow. Synthetic licensing flags are test inputs only; input declarations do not prove actual licensing or source authenticity.
- All seven evidence layers are mandatory. Disagreement, stale/future/missing evidence, event blackout, invalid geometry or risk block the research candidate. Every result remains `signal: WAIT`, `executable: false`, including a fully aligned research candidate.
- Position sizing includes stop distance, spread, declared slippage, commissions, point value and lot rounding; maximum 0.5% per observation and 2% daily loss ceiling. Kill switch and one-active-trade checks are required. The caller supplies account state: this is not an authoritative concurrent account ledger or order manager.
- Monitoring returns each layer and explicit gate failures. Offline replay stores input and result atomically in local SQLite with content-addressed duplicate suppression across restart. HTTP is stateless and does not persist uploads.
- Arabic file-upload UI, synthetic fixture, HTTP boundary tests, deterministic replay/audit tests, positive candidate and independent veto tests, CI integration.

## Verification

- Coordinator Python discovery: 39 tests passing.
- App Python: 20 tests, 4 skipped because optional fixture-dependent cases are unavailable.
- All 9 `coordinator/test_*.js` scripts pass (run from `coordinator`).
- Package manifest: all 26 hashes match; frozen V2 untouched.
- Actual Docker build and standby restart pass; runtime network disabled, provider and worker disabled, volume persists.
- Local Chromium upload/API/render smoke; screenshot `/tmp/gold-ultimate-ui.png` (session artifact).
- Socket-dependent tests require execution outside the inner sandbox; inside it localhost sockets fail with EPERM. GitHub also requires the approved outer execution path because the inner sandbox cannot reach proxy:8080.

## Remaining work before any Ultimate trading release

No live/paid feeds or execution have been enabled. Real DXY/yields/GC provenance and cross-market timing, licensed exchange footprint/depth, verified calendar/headline ingestion, DST/holiday/session-gap policy, calibrated CHoCH and signal weights remain unvalidated. Realistic broker bid/ask fills, persistent account-level risk enforcement and Ultimate paper entry/exit integration are not delivered by this batch. Existing V2 paper worker is unchanged.

The contract's statistical gate remains open: rolling walk-forward, untouched holdouts, regime analysis, net execution-cost sensitivity, bootstrap intervals, and comparisons to V2/naive benchmarks need suitable recorded datasets. Synthetic acceptance tests prove engineering behavior only. No win-rate, profitability, or live-readiness claims are made.

Production, Render, protected branches, Twelve Data, MT5 and subscriptions were not changed or activated. Do not connect this offline evaluator to automatic execution.
