# BiQuote + lowest-cost macro sources — review 2026-11-13

This records a rights/readiness audit. No vendor API calls, secret reads, paper
orders, subscriptions or Render deployments were made.

## BiQuote / XAUUSD
The prepared offline bridge validates a supplied BiQuote quote and OHLC sample,
stages closed bars through the **existing** provider-neutral intake gate with
SourcePolicy disabled and an intentionally absent independently verified UTC
session calendar. Its corresponding paper-admission gate always denies entries.
The V3 / Ultimate engines remain **not invoked** until separately authorized.

Await written BiQuote confirmation of underlying MT5/feed rights for private
Render algorithmic research, historical candle basis (BID/ASK/MID), session
boundaries, bar closure and quote parity. Vendor flags cannot certify rights.

## Official free partial context
- Federal Reserve monetary policy RSS (official headlines only, NOT full news):
  https://www.federalreserve.gov/feeds/feeds.htm
- BLS publication schedule (release times, NOT consensus or surprise):
  https://www.bls.gov/schedule/news_release/
- Federal Reserve H.15 2-year / 10-year Treasury **daily** yields. They do
  NOT substitute for intraday US02Y/US10Y confirmation:
  https://www.federalreserve.gov/releases/h15/
- Existing official source adapters are retained; completeness is not proven.

## Real-time DXY, GC and order flow
- ICE administers DXY; live index data are a distinct product with separate
  access and use rights. No free licensable private Render feed is verified:
  https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-currency-indices
- CME website GC quotes are at least 10 minutes delayed and for reference.
  Their appearance on a web page does not supply real-time GC or licensed
  trades/footprint/DOM data:
  https://www.cmegroup.com/trading/about-quotes.html
- CME real-time market data APIs have separate entitlement and licence steps:
  https://www.cmegroup.com/market-data/market-data-api.html

Conclusion: official partial headline/calendar/yield context can remain
research-only. DXY/GC/true order flow/full global geopolitical and economic
calendar data are MISSING as validated live inputs. No BUY/SELL is authorized.


## 16 November 2026: Direct BiQuote support response and bounded public verification

BiQuote support confirmed that **under its own Terms**, private single-user
Render retrieval, storage, indicators, backtesting and paper-only signals without
public raw redistribution are permitted. **They cannot warrant the rights of
the underlying MT5 broker**, so this is not an independent upstream licence
verification. Public official docs: https://biquote.io/docs/ ;
terms supplied by support: https://biquote.io/terms .

BiQuote also specified:
- Live BID/ASK ticks and the three OHLC frames derive from one MT5 broker feed,
  not Yahoo-blended live candles. **Live-built bars are MID**, calculated as
  (bid+ask)/2. If a series starts empty, it may first be seeded once from
  broker **BID** history. Therefore never label all OHLC BID and never use it
  to calculate actual historical spread or to justify entry/exit costs.
- Approximate retained **closed** bars: M15 192 (~2 days); H1 168 (~1 week);
  H4 180 (~1 month). No missed-period backfill, no continuous-coverage SLA.
  A large reliable independent historical BID/ASK set is still absent.
- They reported UTC-aligned bars, with broker weekly/daily trading breaks
  and possible DST shifts. No-tick periods produce **no candle**. An
  independently verified schedule is still required; do not fill gaps.
- No key or recurring fee, 15,000 requests/min/IP and public read-only
  quote and OHLC endpoints. A rate-limit allowance is not a recommendation
  to poll frequently; official docs prefer the SignalR stream.

**What this changes:** The research adapter now records the direct
support permission and specific MID/BID-seed warning while still blocking
independent broker-rights proof, spread/CFI price parity, and BUY/SELL. Quote
timestamps even 1ms in the future are rejected. We added a one-shot
public read-only probe consisting of exactly **4 bounded GETs** (one quote
plus M15/H1/H4). It is run in a separate GitHub Actions review-only
workflow when that workflow file is first introduced (or explicitly
dispatched), with no key, no MT5, no persistence or orders.

No provider connection or market-data ingestion is active in the production
service. The probe's HTTP result, whether valid or blocked, does not authorize
paper trading and does not count as 24/5 feed stability proof.

**Distinct long-term plan:** BiQuote is an eligible free **research-only
observation candidate**, not a validated primary BID/ASK historical feed or
replacement for GC/COMEX order flow. Capital.com Demo is a potential
independent historical BID/ASK complement after its separate pending
Render data rights and trading-key security questions are resolved.
