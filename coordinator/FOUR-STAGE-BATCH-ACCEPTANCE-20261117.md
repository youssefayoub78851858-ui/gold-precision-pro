# Gold Precision Pro Ultimate — four-stage batch handoff, 17 Nov 2026

**Environment:** GitHub branch `review/v2-portable-tests-20261109` ONLY.
**Zero live trading / zero new subscriptions / zero production deploys.**

## Delivered together

| Stage | Code and regression result | Real-world admissibility |
|---|---|---|
| 1. XAUUSD source quality | BiQuote fixed endpoint failure-class diagnostics and overlapping M15/H1/H4 OHLC audit, 24h final-report parser, stale-quote check and session-reference flags | **BLOCKED** — 29 incomplete sample slots and 0 complete structural audit passes from Nov 16–17; 29 clustered 22:03–22:59 UTC (vendor-declared break, broker not independently verified) |
| 2. Private forward archive | Persistent private owner-only closed-bar vault, revision/hash check, duplicate and time filters, safe metadata counters, quarantine of impossible OHLC subsets and 21-H4 warmup guard | **NOT PROVEN RUNNING** — review tests use synthetic candles; no live forward bars/continuous 24x5 collection verified |
| 3. Frozen V3 + confirmations | Offline `ultimate_four_stage_review.js` run from private forward history when fresh/contiguous, `ultimate_batch_acceptance.py` composes source, vault, technical watch and context vetoes | **RESEARCH ONLY** — real GC/DXY/US02Y/US10Y/Order Flow/calendar/news rights, timing and feed verification incomplete |
| 4. Risk, paper and mobile | `assess_biquote_paper_gate`, `paper_cost_preflight`, integrated four-stage no-order regression tests, Android stage dashboard and strictly sanitised authenticated Coordinator status | **BLOCKED** — real spread/slippage/commission/contract, paper sample fills and untouched forward net performance not independently verified |

## Unified offline acceptance contract

`coordinator/ultimate_batch_acceptance.py` **never** fetches a feed, sends
broker orders, schedules observation, opens paper-ledger files, stores
candles, or claims paper profitability. It inspects owner-only archive
metadata and frozen V3 shadow only. Input historical review metadata is
optional; when omitted it explicitly reports **unverified** rather than
pretending the completed observation was read.

Output includes safe stage status/counts and blockers only, **never raw
quotes, OHLC, entry prices, credentials, trade order plans or PnL**.
Every mode reports top-level `signal=WAIT`, `executable=false`,
`paperOrdersAllowed=false`, `liveOrdersAllowed=false`. Precomputed
owner status is reused without a second V3 invocation. The private
status proxy whitelists only safe stage enums and counts.

Local offline verification (all synthetic fixture prices, no HTTP):
```sh
cd coordinator
python3 -m unittest -v test_ultimate_batch_acceptance \
  test_biquote_private_forward_vault test_biquote_forward_shadow_review \
  test_biquote_24h_final_verdict test_paper_admission_gate
cd ..
node coordinator/test_review_monitor_proxy.js
node coordinator/test_ultimate_four_stage_review.js
```

The entire docker/CI check additionally runs source/parity/entrypoint and
paper no-order simulations. Passing these tests **does not mean the
strategy has a known win rate**, that the upstream broker's rights have
been granted, or that published dashboards reflect live market trades.

## Alternative source shortlisted without payment

Massive Currencies Starter was verified against the current Massive public
currency product/docs and a support answer on 16 November 2026:
**$49/month**, includes real-time Forex WebSocket BBO quotes and historical
Forex quotes, under an individual-use personal terms regime. Massive notes
its Forex aggregates are BID-derived, so they cannot substitute for
historical executable BID/ASK without a separate quote reconstruction.

- Product/plans: https://massive.com/pricing?product=currencies
- Quote WebSocket: https://massive.com/docs/websocket/forex/quotes
- Historical quote docs: https://massive.com/docs/flat-files/forex/quotes
- Personal cloud usage: https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app
- Personal market-data terms: https://massive.com/legal/market-data-terms-of-service

**Not purchased, not linked, no API key used, not production eligible.**
The exact historical `C:XAUUSD` BID/ASK dates, hourly completeness and
quote/aggregate parity have not been proven by an independent authorized
data sample. Massive does not supply COMEX GC MBO/MBP Order Flow in that
Forex quote tier; Databento/CME fees and exchange rights remain
**separate and unresolved**. This plan is a *fallback candidate*, not
a claimed one-subscription solution for the entire trading system.

## Why there is no safe one-click 'activate all'

The historical review's 29 failures are known to occur only in the
provider-declared daily pause, but the precise underlying MT5 broker
calendar has not been independently attested. The 2,051 partial H4
comparisons repeat across snapshots and are not 2,051 unique bad bars.
Zero completed-frame price differences in sampled windows does not
certify all session hours. The 183.859-second max independent quote
age also exceeds the 30-second freshness policy, while all 691
successfully fetched snapshots failed full structural qualification.

The future forward archive had a **separate time boundary set prior to
testing (18 Nov 2026 00:00 UTC)**. No pre-boundary bars may be
retroactively injected or relabelled as prospective. At least 21
**contiguous** H4 closed bars (84 h in a 24h market, longer with
session breaks) plus independently confirmed rights/context/cost are
needed before the frozen V3 watch can become a candidate for validation.
A one-day run cannot supply those bars.

**No coordinator redeploy or environment-variable alteration is
authorized by the batch code itself.** In particular:
- Do not enable `CUTOVER_MODE=live` or place a trade.
- Do not set `GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE` merely because
  the offline suite passes.
- Do not publish `MONITOR_READONLY_TOKEN`, quotes, candles, or broker IDs.
- Do not declare automatic paper-admission; it requires independent
  price/rights/cost checks, preregistered prospective evidence and
  explicit approval.

## Next operational gates requiring outside evidence

Confirm written broker-session/underlying data entitlement, then conduct
a separately approved, fixed-duration, non-trading source-quality check
or source replacement with resilient fresh BID/ASK and fully closed M15,
H1, H4, including gaps. Once qualified, enable a dedicated private
forward archive **after owner approval**, measure required untouched
bars and build independent technical/context confirmations. After that,
run paper results with real spread and commission assumptions and
preregistered success/drawdown thresholds. Before any real trade there
is a distinct broker execution/risk approval step.

This is an implementation and qualification handoff, **not a claim of
four fully operational live trading stages**.
