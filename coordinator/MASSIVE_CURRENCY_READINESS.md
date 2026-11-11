# Massive Currencies: XAU/USD readiness (checked 2026-11-11)

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

Official references:

[Currencies plans and pricing](https://massive.com/pricing)
- [Currencies coverage and C:XAUUSD](https://massive.com/knowledge-base/article/what-markets-do-you-cover)
- [Forex Custom Bars](https://massive.com/docs/rest/forex/aggregates/custom-bars)
- [Individuals Terms, Section 7](https://massive.com/legal/individuals-terms-of-service)
- [Market Data Terms](https://massive.com/legal/market-data-terms-of-service)
- [Displaying data in a personal app](https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-data-in-my-own-app)

Prices and docs can change; check the current order/entitlement screen before
any later approval. This review is not legal advice or a provider confirmation.
