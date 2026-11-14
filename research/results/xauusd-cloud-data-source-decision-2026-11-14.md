# XAUUSD licensed cloud-feed decision — 2026-11-14

## Scope and constraints
Personal, private single-user Gold Precision Pro Ultimate research / paper testing
on Render. Closed M15/H1/H4 Bid/Ask with enough H4 history, reliable clock/session
semantics. No public price redistribution, trading, credentials or paid plans
without the user's explicit consent. No changes to main, backup-v1,
fix-analysis-v2, private or production Render.

This is **a pre-purchase / pre-account decision**, not live connectivity
validation. All engine signals remain WAIT and executable:false.

## Ranked providers based on public documentation

1. FXCM ForexConnect — first low-cost verification candidate.
   The official provider states the SDK is free, supports Linux, live feed and
   history, and uses demo or live Trading Station credentials; official
   FXCM GitHub says EULA signature is required before use.
   Existing Linux static ABI/C++ compilation/linkage CI proves only that the
   official archive is plausibly usable, NOT login or price quality.
   Still require **written** approval of private Render cloud use and local
   quote/candle storage, an account that cannot place orders (or a separately
   reviewed broker isolation design), demo eligibility without deposit/card,
   clock/session rules, and instrument coverage. Current state: NOT CONNECTED.
   Docs:
   https://www.fxcm.com/markets/algorithmic-trading/market-data/
   https://github.com/fxcm/ForexConnectAPI

2. Exness Trader API — technical alternative, NOT proven deposit-free.
   Official docs support hostable REST/WebSocket market data, historical
   Bid/Ask candle requests and Trading read access. It requires Exness
   account eligibility and identity/address verification. Regional
   Arabic help specifically lists a first-deposit requirement; the later
   English help does not explicitly list it. Treat deposit-free eligibility
   as UNVERIFIED, not free. Need read-only key scope verified in an eligible
   account, personal Render rights, data retention rules, actual XAUUSD
   instrument and true-history parity. Do not create accounts or KYC.
   Docs:
   https://get.exness.help/hc/en-us/articles/27866287512476-Exness-API
   https://get.exness.help/hc/ar/articles/27866287512476-%D9%88%D8%A7%D8%AC%D9%87%D8%A9-%D8%A8%D8%B1%D9%85%D8%AC%D8%A9-%D8%AA%D8%B7%D8%A8%D9%8A%D9%82%D8%A7%D8%AA-Exness
   https://www.exness-api.com/trading/guides/code-examples
   https://www.exness-api.com/reference/trading/get-candle-history

3. EODHD EOD + Intraday All World Extended — paid fallback, $29.99/month
   listed for personal plans, including Forex WebSocket and intraday data.
   Do not assume live Bid/Ask WebSocket snapshots match historical intraday
   OHLC price basis or sessions. The independent historical-quote parity
   prerequisite is not established and must be proven before using REST
   candles to warm a real-time research engine. Avoid purchase solely
   because WebSocket has XAUUSD. No paid token request has been made.
   Docs:
   https://eodhd.com/pricing
   https://eodhd.com/help/plans

4. Twelve Data — the Grow commodity data plan is shown at $79/month,
   outside the requested minimum-cost approach, with personal vs
   internal non-display entitlement to be clarified before internal
   trading-research processing. Do not activate.
   https://twelvedata.com/pricing

5. OANDA practice v20 — technically capable of bid/ask candle queries,
   but access/token can control trading accounts and docs warn history
   may differ from an account-specific live price stream. Regional account
   eligibility and private cloud licensing not established.
   https://help.oanda.com/us/en/faqs/api-user-guide.htm
   https://developer.oanda.com/rest-live-v20/introduction/

## Hard decision
**FXCM free Demo is the first candidate to resolve with written provider
confirmation.** At this point no suitable feed is actually authorized and
working end-to-end. The next real activation hinge is a reply resolving
cloud usage/EULA, trading-disabled Demo security, timestamp/quote basis,
XAUUSD Bid/Ask history and no-deposit availability.

Do not pay EODHD, Exness or Twelve Data yet. Do not assume paid activation
would provide every remaining macro/order-flow/news layer or validate the
strategy. The already active separate support-reply monitoring should
be used for updates; do not duplicate prior vendor inquiries needlessly.

No source credentials, private provider-email bodies, broker data, payments,
real SDK session, or provider requests are in this document.
