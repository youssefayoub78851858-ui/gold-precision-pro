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

1. FXCM ForexConnect — technically prepared, but not an accessible primary candidate for Lebanon registration.
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

2. Exness Trader API — technical alternative; currently unavailable on the Lebanon registration path.
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

3. EODHD EOD + Intraday All World Extended — primary paid forward-collection candidate, $29.99/month
   listed for personal plans, including Forex WebSocket and intraday data.
   Provider support confirmed XAUUSD live Bid/Ask WebSocket, and private
   single-user Render research/storage rights. Historical 1-minute intraday
   XAUUSD.FOREX OHLC is updated the following day, has an unspecified price
   basis, and is NOT from the same feed; no separate historical Bid/Ask archive.
   Therefore it cannot warm the live Bid/Ask research engine as if comparable.
   Collect authentic, continuously observed closed BID/ASK M15/H1/H4 bars
   forward only after explicit subscription, source and private deployment
   approval. No paid token request has been made.
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

## Hard decision — updated after keyless real HTTP/JSON tests
**For an independent private Render stream, EODHD $29.99/mo is the lowest-priced
candidate in this comparison whose provider has explicitly confirmed XAUUSD live
BID/ASK streaming and the intended private research/storage rights.** It is NOT
yet a validated continuously connected feed, nor sufficient for a complete
historical BID/ASK backtest from day one. A trial subscription would require
prior user approval and a separate approved private deployment.

Gold API Premium is cheaper at **$10/mo**, but its /ohlc endpoint returns ONE
OHLC summary per arbitrary range, not native ready-made M15/H1/H4 historical
series; /history minute/hour groupings return min/max/avg, not full OHLC.
Unknown closed-bar finalization, session calendar, true quote basis, Bid/Ask
parity and historical availability make it **not purchase-ready** for this
BID/ASK paper engine. Gold API free public price is display-only.

Actual public one-shot GitHub Actions 43613079168:
GET Gold API /symbols => HTTP 200 JSON, /price/XAU => HTTP 200 JSON.
No-key Gold API /ohlc/XAU and /history => HTTP 401 JSON
{"error":"No x-api-key header."}. EODHD demo-token XAUUSD intraday
=> HTTP 403 Forbidden (text/html); no licensed XAUUSD OHLC obtained.
No payment, account, trade, secret or Render deployment.

The submitted FXCM and Exness account registration paths both reject
Lebanon residence. Do not request a different country of residence.
All strategies remain WAIT/executable:false until source validation,
data continuity, independent UTC session rules and risk controls pass.

Do not pay EODHD, Exness or Twelve Data yet. Do not assume paid activation
would provide every remaining macro/order-flow/news layer or validate the
strategy. The already active separate support-reply monitoring should
be used for updates; do not duplicate prior vendor inquiries needlessly.

No source credentials, private provider-email bodies, broker data, payments,
real SDK session, or provider requests are in this document.


### Additional official Gold API references (reviewed 2026-11-14)
- https://gold-api.com/llms.txt
- https://gold-api.com/pricing
- https://gold-api.com/terms
- Actual HTTP probe: https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/43613079168
