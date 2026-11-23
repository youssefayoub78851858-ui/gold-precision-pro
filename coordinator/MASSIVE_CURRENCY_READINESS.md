# Massive Currencies: XAU/USD readiness (checked 2026-11-16 (review only))

This is a documentation review only. No account, key, subscription, API request,
or provider connection was used. `massive_xauusd_fixture_adapter.py` only
normalizes explicitly synthetic Massive-shaped fixtures; it cannot call Massive.

## Instrument and intervals

Massive documents spot gold as `C:XAUUSD` in its Currencies data. Its Forex
Custom Bars endpoint uses multiplier/timespan aggregates, so M15 maps to
15/minute, H1 to 1/hour, and H4 to 4/hour. Currency bars derive from quotes,
not centralized executed trades. The `v` field must not be treated as traded
volume; the adapter intentionally omits it. The feed gate still requires closed,
aligned, fresh bars and an expected-session schedule, and it never fills gaps.

## Plan and rights boundary

- Basic: $0/month; 5 API calls/minute; up to 2 years of history; EOD currency
  data. This is not suitable for a current intraday monitoring loop.
- Starter: $49/month as listed for monthly billing; real-time currency data,
  unlimited API calls, and 10+ years of history. It was not purchased or tested.
- The Currencies catalog includes precious metals and lists C:XAUUSD. This
  confirms documented coverage, not the account's exact entitlement or a
  guarantee of continuous/gap-free bars.
- Individual terms limit use to personal, non-commercial, non-business purposes.
  Terms say a hosting provider may process Information only on the user's behalf
  and within the user's rights, and must not use it itself or expose it to others.
  Therefore a private single-user Render service appears compatible in principle,
  but the terms do not explicitly confirm this project's Render storage, backups,
  derived output, retention duration, or the exact C:XAUUSD entitlement. Those
  remain unverified; do not attach credentials or admit data until confirmed.

## No-purchase acceptance: synthetic adapter-to-intake wiring (2026-11-23)

`coordinator/massive_pre_purchase_handoff.py` feeds the existing
`massive_bbo_history_adapter.review_synthetic_massive_bbo` output
through the **real** `xauusd_feed_gate.intake_payload` and
`xauusd_research_pipeline.run_research_pipeline` interfaces, with
all inputs expressly `SYNTHETIC_TEST_ONLY`. It does not create
REST/WebSocket connections, credentials, subscriptions, paper journals,
trading orders or network requests.

In the isolated local acceptance fixture, 12,000 fictional quotes form
800 closed M15, 200 H1 and 50 H4 bars. Removing **one** internal quote
creates a 120-second interval and drops that M15, its H1 and its H4,
leaving 799 / 199 / 49 respectively. This is a resilience test, not
proof that the advertised real 2026 history contains even a single
complete H4 or an ASK observation.

The existing intake recognizes mock data as synthetic only; the V3/r2
and paper engines are **SKIPPED**, even if the test includes 50 H4
groups. The same bars relabelled `recorded` must fail the
unentitled `SourcePolicy`. An old batch, forged rights,
wrong ticker, crossed quote, invalid timestamp, environmental approval
flags or absent M15 coverage cannot authorize a trade or paid request.
The sample contains an **assumed weekend gap**, not an authenticated
Massive/broker trading calendar. This and synthetic paper exercises
never prove real account entitlement or future win rate.

**Actual purchase decision: NOT APPROVED.** No plan purchase, billed
provider request, Render deployment or live signal is allowed by a
passing CI job. Request legitimate non-billable evidence of 2026
`C:XAUUSD` historical BID+ASK density in each Aug/Sep/Oct window and
actual Starter entitlement, then independently verify source rights,
session schedule, quote chronology, cross-frame BID/ASK parity,
current stream continuity, and prospective broker-cost paper results.
If no permitted free sample is available, report this as the remaining
*external commercial risk*, not an internal test passing.

## Historical coverage caveat (provider documentation; 2026-11-16)

Massive's Currencies FAQ documents that gold `C:XAUUSD` starts from
historical records dated 2009-09-27, but it also warns that
gold is mostly missing for 2010-07 through 2013-07 and that gold/silver
forex quotes were **sparse during 2021-01 through 2025-08**. This is a
provider-wide caveat, not a measurement of our account or any 2026 dates.
The advertised "all history" does **not** mean continuous BBO coverage.

Before purchasing Starter or asking an operator to connect actual credentials,
obtain written provider-level confirmation or a documented, explicitly
authorized **non-billable** sample/coverage report for `C:XAUUSD`, separately
for 2026-08, 2026-09 and 2026-10 (the planned chronological holdout windows).
Verify that `/v3/quotes/C:XAUUSD` actually exposes **both** BID and ASK
with independent market timestamps on the intended plan, not only bid-derived
OHLC aggregates. Check actual quote density, closure and weekend/session gaps,
fifty complete H4 bars, 90-second in-session gaps, current WS same-instrument
quotes, and the private one-user Render research/storage rights. An empty
response must never be treated as a successful coverage or parity check.
If a non-billable sample is unavailable, mark this gate `BLOCKED` rather
than paying, guessing or substituting quote counts for trade volume.

References:
- [Massive Currencies FAQ, historical coverage](https://massive.com/knowledge-base/categories/currencies)
- [Historical forex BBO quotes endpoint](https://massive.com/docs/rest/forex/quotes/quotes)
- [Currencies plan entitlements](https://massive.com/currencies)

**No 2026 XAUUSD BBO coverage has been independently established by this
documentation review, and no credential, network API call, charge, paper
order or live execution is authorized.**

Official references:

[Currencies plans and pricing](https://massive.com/pricing)
- [Currencies coverage and C:XAUUSD](https://massive.com/knowledge-base/article/what-markets-do-you-cover)
- [Forex Custom Bars](https://massive.com/docs/rest/forex/aggregates/custom-bars)
- [Individuals Terms, Section 7](https://massive.com/legal/individuals-terms-of-service)
- [Market Data Terms](https://massive.com/legal/market-data-terms-of-service)
- [Displaying data in a personal app](https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-data-in-my-own-app)

Prices and docs can change; check the current order/entitlement screen before
any later approval. This review is not legal advice or a provider confirmation.
