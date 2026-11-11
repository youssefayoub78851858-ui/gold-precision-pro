# XAUUSD cloud feed decision — 2026-11-11

## Decision

There is no source currently verified as both authorized and operational for continuous XAU/USD M15/H1/H4 intake in this project. Keep live ingestion disabled and the analysis result at `WAIT`. No vendor API request, trial activation, account opening, or payment was made.

## Best candidate to resolve next: Twelve Data XAU/USD

Twelve Data is the closest cloud-hosted candidate found. Its documentation lists `15min`, `1h`, and `4h` time-series intervals, classifies XAU/USD as a commodity, and says the time-series endpoint is available starting with Basic. A separate Forex API v2 description includes precious metals, so product/plan classification needs confirmation for the exact XAU/USD symbol. Its published REST OHLC timing can lag a candle close by roughly 0.3–2 minutes depending on instrument. These pages establish a technical candidate, not a continuous-feed acceptance test.

The plan/rights pages create a material entitlement ambiguity:

- Basic is advertised at $0/month with 8 API credits/minute and 800/day. Its plan page describes internal non-display usage; that is not enough to authorize displaying the price or derived signal in this app.
- Grow is advertised at $79/month and explicitly includes commodity market data and internal display access. This is the lowest displayed individual tier that clearly names both. Individual plans are limited to individual, non-commercial use. The published terms still do not establish that this exact XAU/USD entitlement permits a Render-hosted private dashboard, automated analysis, and our intended retention. We have not obtained written confirmation or accepted a paid plan.
- The WebSocket allowance on lower plans is trial access, not a verified continuous OHLC stream. REST polling is technically possible, but continuity, revisions, service availability, and account-specific entitlements have not been tested.
- One M15 request every 15 minutes would be 96 requests/day (calculated), under Basic's published daily quota, but quota alone does not satisfy data rights or reliability requirements. H1/H4 should be derived only from complete UTC M15 bars unless the provider contract and data quality independently validate native bars.

**Recommendation:** Twelve Data Grow is the best technical/licensing candidate to ask about, but it is not yet an approved or proven source for this project. Ask Twelve Data to confirm in writing whether the $79/month individual Grow plan covers this exact XAU/USD instrument, closed-bar history, private Render hosting, internal display, automated research use, and retention. Basic is free and has the higher uncertainty around commodity entitlements and display. Do not start a trial or send a market-data request until the user authorizes the provider action and, if applicable, the cost.

## Alternatives and constraints

- **OANDA v20:** its official API comparison says v20 is unavailable to OANDA Global Markets. The reviewed material does not confirm a Lebanon-resident account division that would provide v20 candle access. It is not a validated fallback. No account was opened and no terms were accepted.
- **COMEX GC:** remains an independent confirmation source, not a substitute for spot XAU/USD. CME licensing rules apply to non-display use even when delayed data comes through a distributor. No GC license or account entitlement is verified; exact fee depends on product, use, and distributor and must be quoted before activation.
- **Dukascopy:** prior source-specific permission is unresolved; no automatic download has been started.
- **Android-only / cloud hosting:** a cloud receiver avoids a personal computer, but Render's free web service can sleep after inactivity and free Background Worker/Cron options are unavailable. Therefore the free Render setup cannot promise an always-on polling loop. No Render service/configuration was changed. The receiver code is prepared but not connected to a provider or HTTP route.

## Implementation and test status

`coordinator/xauusd_feed_gate.py` provides a provider-neutral, offline intake contract:

- HMAC-SHA256 packet authentication, bounded timestamp skew, nonce replay rejection, and no secret persistence.
- UTC-only timestamps, interval alignment, OHLC sanity, explicit provider session schedule, closed-bar and freshness checks for M15/H1/H4.
- Any missing scheduled candle, duplicate, stale/unfinished bar, provider mismatch, or unapproved entitlement blocks the whole batch.
- Exponential retry-delay calculation is bounded; this code does not initiate network retries.
- Outputs always include `signal: WAIT` and `executable: false`, including accepted test packets.

Seven offline unit tests use fabricated unit fixtures only. They test valid normalized frames, gaps, forming/stale bars, duplicates, invalid OHLC, signature tampering/replay, timestamps, source mismatch, and outage backoff. They make zero vendor requests. The module is not yet wired to an HTTP endpoint, durable shared replay store, persistent production store, or provider adapter; deployment requires approved source rights and a separately authorized service change.

## Official references reviewed

- https://twelvedata.com/pricing
- https://twelvedata.com/markets/commodities/xau-usd
- https://twelvedata.com/docs#time-series
- https://support.twelvedata.com/en/articles/5615848-how-fast-is-your-data
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage
- https://support.twelvedata.com/en/articles/12520817-forex-api-v2
- https://twelvedata.com/terms
- https://developer.oanda.com/rest-live-v20/api-comparison/
- https://www.cmegroup.com/market-data/real-time-and-historical-data.html
- https://www.cmegroup.com/market-data/distributor/market-data-policy.html
- https://render.com/docs/free
- https://render.com/pricing
