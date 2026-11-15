# Historical XAUUSD bootstrapping gate — review only

Date: 2026-11-15. No provider tokens, requests, account messages, or quotes committed.

## Public evidence and conservative engineering decision

EODHD's public [Intraday API documentation](https://eodhd.com/financial-apis/intraday-historical-data-api)
describes intraday OHLCV bars. Its [WebSocket documentation](https://eodhd.com/financial-apis/new-real-time-data-api-websockets)
describes separate real-time Forex bid/ask stream. The
[personal pricing page](https://eodhd.com/pricing/) lists
EOD + Intraday All-World Extended at USD 29.99/month.

Those public materials do **not establish** that historical OHLCV bars are
historical BID/ASK from the same stream, with the same quoting convention
and first-publication timestamp. Thus the research gate must not promote
historical single-series OHLCV to verified historical BID/ASK, regardless
of numeric proximity or number of H4 bars.

## Immutable pre-purchase requirements

- No REST-to-WebSocket BID/ASK merge, even with 800+ M15 or 50+ H4 bars.
- Historical single-series data can be evaluated *separately*, if verified,
  using explicitly labeled research methodology and an appropriate cost model.
- The stream's own validated, completed BID/ASK bars can build forward history.
- At least 50 complete H4 bars require 800 valid aligned M15 building blocks
  in the ideal continuous case, 200 covered market hours. Outages, session
  calendars and partial boundaries can increase elapsed collection time.
- Quote freshness, licenses, independent session calendar, correct bid/ask
  basis, spread/CFI broker parity, safe private storage and a separate
  research admission decision are all required in addition to bar counts.
- Licensed personal feed cannot be sent to the publicly viewable review
  dashboard. A separate authenticated, single-user service is needed.
- All automated execution remains disabled. Research continues with WAIT.

**This note contains only public documentation and code-level engineering
restrictions; no private support email contents, addresses, or account data.**

Tests:
`python -m unittest -v test_eodhd_bootstrap_preflight test_pre_subscription_preflight`
and the existing review HTTP test under GitHub Actions.

Next most valuable *free* task: independently verify a compatible
same-source historical BID/ASK option or confirm that forward-only
collection time/cost is acceptable before subscribing; do not guess one.
