# Gold Precision Pro Ultimate — Work completed before upstream BiQuote reply

**Branch:** `review/v2-portable-tests-20261109` only.
**Status:** protected research/demo, **WAIT / executable=false**.
**No subscription, paid provider calls, broker orders, production deployment, or
private Coordinator archive activation.**

## Four coordinated workstreams

| Stage | Implemented and tested | Remaining external evidence |
|---|---|---|
| XAUUSD data | Credential-free fixed BiQuote quote/M15/H1/H4 one-shot, endpoint failure categories, independent quote-clock freshness, H1/H4 OHLC overlap and vendor-reference vs unexplained missing slots | Upstream MT5 broker identity/entitlement, independent session/DST calendar, continuity across new market-open windows, Bid/Ask history for actual execution |
| Private history | Owner-only durable vault with 18 Nov 2026 forward holdout, no backfills or revised closed bars, metadata and 21-contiguous-H4 warmup, protected batch status; **new** static retention-capacity preflight | Explicit activation only after source qualification; actual prospective saved bars and zero data gaps not shown by offline tests |
| V3/context | Frozen V3 analysis of only closed contiguous bars, source/UTC/overlap rules, no trade promotion, 4-stage integrated diagnostic | Independent current DXY/US02Y/US10Y, GC, calendar/news, licensed Order Flow, and their validity/timing; no fabricated substitute |
| Paper / money | Risk and cost model for **synthetic** scenarios, paper-ledger tests, WAIT gate, protected entry/stop/target suppression, Android review and private status | Broker's contract sizing, spread/commission/slippage, paper forward sample and net out-of-sample expectancy before live orders |

## No-surprise archive capacity

`private_forward_capacity_preflight.py` validates already trusted owner-only
metadata, **not raw prices**. The current single-file private vault enforces:

- **10,000** distinct quote observations maximum; at a *hypothetical* single
  unique observation every 2 minutes that corresponds to 333.3 hours (13.9
  continuous days) with **no claim of real uptime or market availability**.
- **45,000** closed bars maximum per M15, H1 and H4 timeframe, separately.
- Status **CAPACITY_HEADROOM**, **CAPACITY_WARNING** at >=80% of any limit,
  **CAPACITY_LIMIT_REACHED** at any full hard cap, and
  **CAPACITY_METADATA_UNAVAILABLE** for missing/untrusted owner metadata.
- The four-stage status and Android private monitor report quote remaining and
  explicit blocked states, with falsified or impossible counts rejected.
- No silent FIFO rotation, deletion, compression, migration, quote
  replacement or reset is authorized or coded. Extending a long-running
  archival history requires a separately reviewed retention/partition policy
  and sufficient durable storage.

**Important:** The 10,000-quote limit does not by itself supply sufficient
forward return/volatility evidence for a profitable system, and holding
MID candle prices is not the same as a historical BID+ASK execution tape.

## Actual free source observations, not backtest

- 16–17 Nov 24-hour review: 720/720 samples, 29 incomplete samples during
  provider-declared 22–23 UTC break; 0 fully passed structural samples;
  max independent quote age 183.859 sec; H4 partial groups across snapshots
  are repeated observations, not unique missing candles.
- 18 Nov 06:29 UTC bounded one-shot: **four HTTP+JSON endpoints OK**,
  independent quote age 3.01 sec; fully covered H1 47 and H4 9
  OHLC comparisons, **0 observed disagreement** in those windows.
  H4 had **2** partial groups comprising **8** M15 slots in the vendor's
  reference daily pause; no observed partial OHLC bound contradiction.
  Full structural acceptance still false. No new archive was written.
- Support request sent to BiQuote on 18 Nov 2026 seeking upstream MT5
  broker name/rights, DST/session proof and a Spot/CFD vs CME GC distinction.
  Await its answer; that answer alone may not prove broker rights if support
  disclaims independent authority.

## Independent go/no-go (not an activation instruction)

1. Written broker source and permitted cloud-use evidence.
2. Independently checked session/DST/holiday timing; stale quote and
   missing M15/H1/H4 OHLC tests on new market-open samples.
3. Separate, permissioned owner-only forward vault activation (nothing
   written to GitHub); disk budget and retention policy confirmed.
4. >=21 genuinely prospective **contiguous** closed H4 bars plus aligned
   H1/M15 and multiple fully covered cross-frame OHLC comparisons.
5. Confirm real trading fees/contract and the macro/GC/Order Flow feeds,
   then preregister and measure forward paper orders and losses.
6. Only after reproducible positive **net** out-of-sample results and risk
   approval can execution eligibility be discussed. No guarantees of
   profitable trades, no auto-migration to production.

## Safety and deployment

The review demo is a status UI, not a brokerage connection. At every stage
the decision remains `WAIT`, `executable=false`, `paperOrdersAllowed=false`.
The protected Coordinator was **not redeployed**, its archival activation
environment variable remains unchanged, and the production Render service
continues on its older known SHA.

Representative test commands (offline only):
```bash
cd coordinator
python -m unittest -v test_private_forward_capacity_preflight \
  test_ultimate_batch_acceptance test_biquote_private_forward_vault \
  test_biquote_forward_shadow_review test_paper_cost_preflight
cd ..
node coordinator/test_review_monitor_proxy.js
node test_unified_mobile.js
```
