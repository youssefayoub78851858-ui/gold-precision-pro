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
