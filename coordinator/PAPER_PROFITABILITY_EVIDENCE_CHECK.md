# Gold Precision — paper profitability verification gate (research only)

**Status: NO verified profitable strategy; no live or paper-order authorization.**
No subscriptions, secrets, provider network requests, Render deployment or
real-money trades are made by this change.

## The evidence we actually have

The existing `research/results/ultimate-walkforward.json` is recorded
BID-only research with modeled spread/slippage/commission, not an independently
authenticated new-data holdout. Its baseline scenario reports:

| Chronological window | V2 closed trades | V2 modeled net USD | Ultimate closed trades |
|---|---:|---:|---:|
| Train | 31 | -88.41 | 0 |
| Validation | 24 | -412.33 | 0 |
| Test | 24 | +345.14 | 0 |

Stress costs further change the figures. A positive *test* slice does
not erase negative train and validation outcomes; the three windows
are reused development data, not statistically independent proof.
Ultimate had **zero** closed trades because mandatory GC, DXY, yields,
news and order-flow evidence was absent. Thus neither a 70% hit rate
nor a dependable USD-per-day profit is established.

## A consistent, locked, prospective assessment

`prospective_paper_edge_screen.js` uses the existing
`prospective_paper_holdout_audit.js` with exactly its chronology,
first-observed M15/H1/H4 clocks, USD risk convention and fee accounting.
It **never** reads broker keys, quotes, private journals, or real fills;
it receives caller-supplied sanitized trade observations. Every result
stays `WAIT`, `executable:false`,
`profitableSignalDeploymentApproved:false`, and
`statisticallyVerifiedProfitable:false`.

A future externally verified prospective sample will be assessed against
these unchanged **diagnostic** thresholds (not a trade-admission rule):

- At least **100** fully closed paper trades observed prospectively.
- At least **30 distinct UTC dates** and **6 calendar weeks** within
  the frozen research period of at most **90 calendar days**; if fewer
  trades occur, report **insufficient sample** rather than manufacture
  extra observations.
- Positive net P&L after individually modeled spread, slippage and
  commission, with explicit P&L conventions preventing double-charging.
- Positive total P&L after **2×** those same modeled costs.
- Modeled profit factor **at least 1.2**, with both realized wins
  and realized losses (an all-win dummy fixture is not proof).
- Positive net P&L in each of three *fixed chronological thirds*,
  rather than one lucky end-period winning trade.
- Realized peak-to-trough **drawdown at most 10R** in the *closed-trade*
  path, and positive fifth percentile of 2,000 deterministic UTC-day
  cluster resamples of mean net R. The latter is a descriptive sensitivity
  check, **not a calibrated confidence interval**. It preserves within-day
  but not cross-day market serial dependence. Closed-trade drawdown is
  incomplete when open exposures exist.

**Passing all the numeric thresholds on a fabricated ledger still does
not demonstrate profitability.** Tests explicitly prove this. An
actual claim additionally requires a verifiable immutable strategy
freeze, independent provider rights and identities, a valid broker
session calendar, historical quote and live feed entitlement, recorded
decision-time first-receipt evidence, genuine BID/ASK and broker costs,
a tamper-evident *complete* WAIT/outage/order/position journal,
financing/rollover treatment, and out-of-sample observations collected
AFTER the freeze. No GitHub mock test can attest any of these.

## Current operational answer

Only the **engineering/math** of the profitability screen has been
tested offline. There is currently no valid live-source paper sample
that can establish an edge. The next external step is a licensed
independently timestamped real XAUUSD source, secure private archive
backup, a protected paper journal, then non-cherry-picked forward
evaluation. No BUY/SELL, automatic paper entry or real order should
be promoted merely because an offline test turns green.

Offline check: `node coordinator/test_prospective_paper_edge_screen.js`.
