# Market source review — 2026-11-11

## Decision

No provider was verified as a legally usable, free, continuous XAUUSD M15/H1/H4 candle source for this project. Keep the candle gate closed and return `WAIT`. No authenticated history/OHLC or OANDA API requests were made.

## Gold API

- The unauthenticated `/price/XAU` endpoint is a reference spot quote, updated about every 30 seconds. It is not a broker candle feed and cannot establish closed M15 OHLC bars.
- `/history` and `/ohlc` require an API key from a free account. The free tier shares a limit of 10 requests per hour across those endpoints.
- The provider's published plan describes minute/hour history groupings as Premium. Its public docs do not establish that free OHLC supports M15, closed-bar finalization, interval alignment, or a usable historical depth for a continuous M15/H1/H4 feed. A quota of 10 requests/hour does not establish those properties.
- Terms permit use in web applications but disclaim accuracy, completeness, reliability, and uninterrupted/timely availability. Therefore the no-key spot quote remains display-only; the free OHLC entitlement is not accepted as an analysis source without a documented M15 contract and a controlled test.

Official references:

- https://gold-api.com/faqs
- https://gold-api.com/pricing
- https://gold-api.com/docs
- https://gold-api.com/terms

## OANDA v20 practice API

- OANDA documents practice and live REST/streaming endpoints, historical candles, and an account-specific token. The developer comparison lists M15, H1, and H4 candle granularities.
- Access requires a v20 account, API access, a personal token, and acceptance of the API license. The token is sensitive and grants access to the account's subaccounts; it must not be placed in GitHub.
- OANDA's documentation says v20 is unavailable to OANDA Global Markets and TMS Brokers S.A. The current Global Markets eligibility list does not list Lebanon. The official materials reviewed do not confirm which supported OANDA division, if any, can onboard a Lebanon resident with v20 access.
- Accordingly, OANDA is only a conditional lead, not an eligible or tested source for this project. No account was opened, no terms were accepted, and no requests were sent.

Official references:

- https://developer.oanda.com/rest-live-v20/introduction/
- https://developer.oanda.com/rest-live-v20/api-comparison/
- https://developer.oanda.com/rest-live-v20/development-guide/
- https://developer.oanda.com/rest-live-v20/authentication/
- https://help.oanda.com/bvi/en/faqs/eligible-ogm-countries-bvi.htm
- https://www.oanda.com/region-selector/

## Acceptance gate for any future source

Do not label the feed `live` or enable analysis until a user-authorized, read-only test proves all of the following:

1. Written terms and the account division allow the intended private research/display use.
2. Exact instrument identity and quote convention are known; XAU spot is not silently treated as the CFI broker's XAUUSD or COMEX GC.
3. Native M15, H1, and H4 candles include UTC timestamps, documented boundaries, and closed/final status.
4. Historical depth, freshness, missing intervals, duplicates, and corrections are measured and validated.
5. Request ceilings and shared-cache/deduplication behavior are enforced before any polling.
6. Failure, stale data, incomplete bars, and provider timeouts produce `WAIT` and `executable:false`.
7. A continuous observation period passes without gaps before the source is considered operational.

The existing read-only MT5 exporter remains a local desktop-terminal bridge. It is not connected by Android MT5 and has not produced a continuous feed in the Render demo.
