# EODHD first-month readiness — no subscription (November 2026)

Before paying, we can validate code using **synthetic quotes only**.
The EODHD research bridge requires 50 closed M15/H1/H4 bars per timeframe.
The H4 history cannot geometrically contain 50 complete H4 without at least
800 complete and correctly aligned M15 bars (200 hours of fully covered
four-hour groups), excluding closures, partial groups and missing quotes.

## Offline long-horizon rehearsal
GitHub Actions runs `coordinator/test_eodhd_first_month_replay.js`.
It generates 800 fake closed M15 BID/ASK candles on two aligned
segments, separated by an assumed 48-hour pause for testing only.
The pause is **not** a verified EODHD session calendar. Required checks:
- first segment 480 M15 / 120 H1 / 30 H4; second 320 / 80 / 20
- combined 800 M15 / 200 H1 / 50 H4
- zero interpolated candles across 48-hour gap
- one missing M15 reduces complete H1/H4 counts to 199/49, not 200/50
- cold process restart recovers only closed BID/ASK frames and clears
  auth, any quote freshness, live research and trade readiness
- WAIT and executable:false regardless of all mathematical warmup counts
- no provider requests, token reads, real data, subscriptions, paper orders
  or live broker orders in this test

## Unresolved requirements for any paid one-month test
1. Provider must confirm the actual paid XAUUSD streaming entitlement
   and whether history includes a bid/ask basis compatible with WS.
2. A verified independent UTC session calendar is mandatory. A
   remembered weekend pattern is not enough for historical admission.
3. If paid REST history has no independently compatible bid/ask
   series, EODHD streaming must collect forward from live closed
   quotes; a subscription day alone does not provide 50 H4 candles.
4. First live day checks: auth, bid <= ask, tick clock, closed M15
   continuity, H1/H4 alignment, outage/restart, broker spread and
   source rights; fail closed when a gate is missing.
5. Independently verify external GC, DXY, news, broker costs and live
   output accuracy before calling the Ultimate strategy production-ready.

This rehearsal does not prove real-world OHLC availability, profitability,
continuous uptime, actual pricing, or a usable historical warmup on day 1.
