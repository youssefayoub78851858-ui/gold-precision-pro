# Pre-purchase XAUUSD BID/ASK alternative sources — 2026-11-15

## Decision
**No purchase / provider connection / production modification.** Best *documented*
single-vendor alternative to EODHD is Massive Currencies Starter (`$49/mo`).
Massive's Forex REST historical BBO quotes and realtime WebSocket BBO both cover
the forex asset class, including `C:XAUUSD`. This is **not** yet proof that a
specific paid 2026 historical XAUUSD BBO window has a sufficient number of
continuous aligned M15 BID and ASK bars or that all data are licensed for a
private Render service. Do not release signal WAIT before formal validation.

## Free real-world validation (NOT a paid BBO historical quote pull)
A no-purchase Massive API call against the *free-tier aggregate* endpoint:
`GET /v2/aggs/ticker/C:XAUUSD/range/4/hour/2026-10-26/2026-11-12`
- 86 historical XAUUSD 4-hour OHLC rows retrieved, period 2026-10-26 00:00 UTC
  through 2026-11-12 20:00 UTC.
- All 86 OHLC rows passed a simple high/low/open/close numeric relation check.
- Two observed 48-hour UTC gaps around weekends, no fabricated intervals.
- Massive says its forex OHLC bars are **bid-price-derived**, not ask bars.
- These 86 BID OHLC rows alone **do not prove** 86 historical BID+ASK
  synchronized fully covered H4 bars, 800 aligned M15 samples, any broker-price
  parity, or admission to live trading. Premium historical BBO /v3/quotes
  is not available on the free Basic plan and was NOT requested.
- API response was used only for counts and status, not stored or redistributed.
Official docs:
https://massive.com/knowledge-base/article/how-are-massives-forex-bars-built-and-what-do-v-and-n-mean-on-a-forex-bar
https://massive.com/docs/rest/forex/quotes/quotes
https://massive.com/docs/websocket/forex/quotes
https://massive.com/knowledge-base/article/what-asset-classes-are-availalbe-through-massives-currencies-subscription

## Practical providers
| Candidate | Observed offer | Passes both historical and stream BID/ASK? | Unresolved |
| --- | --- | --- | --- |
| Massive Currencies Starter | $49/mo; historical BBO REST, realtime BBO WebSocket, XAUUSD symbol | Candidate YES by endpoint design, **not verified 2026 matched historical ASK** | Free sample of paid history, 50+ aligned complete H4 BID+ASK and exact quote timestamps, Lebanon account eligibility, internal single-user Render cloud rights, stream uptime and broker variance |
| Dukascopy official JForex | Official historical BID/ASK bars and ticks; API live via authenticated Java SDK | Candidate YES via JForex; DEMO live stream differs from LIVE historical quotes | Cloud licence/eligibility for Lebanon, private headless deployment on Render, account and expense, live-vs-history parity |
| OANDA v20 | Historical `price=BA`; account-specific streaming | PARTIAL: historical base-price group may differ from account-specific live rates | Lebanese account eligibility and API division, actual XAU_USD entitlement, stream parity |
| TraderMade Streaming | £599/mo advertised; bid/ask streaming and REST tick backfill depending on plan | Commercially plausible, **far above budget** | Exact XAUUSD history entitlement, licence and quote |
| EODHD | $29.99/mo, spot XAUUSD bid/ask websocket | NO compatible historical BID/ASK archive documented | Requires streaming forward-only 50 complete H4 (>=800 aligned M15) unless another verified independent matched data source |

Massive prices: https://massive.com/pricing?product=currencies
Massive forex BBO: https://massive.com/docs/rest/forex/quotes/quotes
Massive realtime BBO: https://massive.com/docs/websocket/forex/quotes
Massive personal terms: https://massive.com/legal/market-data-terms-of-service
Dukascopy JForex API: https://www.dukascopy.com/swiss/english/forex/api/jforex-api/
Dukascopy history API: https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/IHistory.html
Dukascopy Demo-vs-Live issue: https://wiki.dukascopy.com/en/development/strategy-api/historical-data/overview-historical-data
OANDA history/live different pricing groups: https://help.oanda.com/us/en/faqs/api-troubleshooting-guide.htm
TraderMade price: https://tradermade.com/pricing

## What $49 does not cover
Massive **Currencies Starter does not include** GC COMEX futures or proprietary
ICE DXY feed. Massive Futures Advanced real-time package advertises $199/mo
separately, and Massive says Level-2 depth is NOT currently available; order flow
/DOM full-depth cannot be assumed in any $49 Currencies plan.
https://massive.com/pricing?product=futures
https://massive.com/knowledge-base/article/does-massive-offer-level-2-data

## Written evidence required before paying
Ask Massive sales/support for:
1. XAUUSD exact historical quote symbol and last-10-trading-days UTC sample
   of `bid_price,ask_price,participant_timestamp`, plus counts enabling
   >=50 fully aligned, closed H4 bars across BID+ASK; max historical tick/quote
   coverage and missing intervals; ask timestamp basis relative to WebSocket.
2. Does the `$49/month Currencies Starter` personal plan include the historical
   XAUUSD quote REST `/v3/quotes` AND real-time `C.XAU-USD` WebSocket quote
   subscription without add-ons, geographic restrictions or separate feeds?
3. Written permission for **private authenticated, single-user, noncommercial
   Render cloud processing/caching/derived technical indicators/paper simulation**,
   and data retention limitations. No public licensed quote display.
4. Whether an anonymized 2026 recent history test sample or trial can be
   supplied without payment card or paid subscription.
5. Exact billing and future GC futures / DXY costs **separately**.

Research status: `WAIT`, `executable:false`. No paid provider data
was fetched, no external broker order, no deployment and no account charges.
