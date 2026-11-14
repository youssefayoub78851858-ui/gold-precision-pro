# Gold API Premium / EODHD no-purchase gate (2026-11-14)

Source: official https://gold-api.com/llms.txt , pricing and terms.

Gold API $10/mo provides a single OHLC object for an arbitrary requested timestamp
range, not native ready-made arrays of 15m/1h/4h finalized bars.
The history endpoint's minute/hour grouping returns min/max/avg aggregations;
these are not a documented bid/ask OHLC candle series.
A possible per-interval OHLC reconstruction would require one independently
scheduled request per complete M15 window, measured finalization, sufficient
historical density and provider provenance. It has NOT been verified.

Actual unauthenticated GitHub Actions public HTTP probe, run 43613079168:
- GET /symbols: HTTP 200 JSON array (7 symbols).
- GET /price/XAU: HTTP 200 JSON XAU spot quote with updatedAt field.
- GET /ohlc/XAU with a 15-minute period, no x-api-key: HTTP 401 JSON
  {"error":"No x-api-key header."}
- GET /history with minute grouping, no key: HTTP 401 JSON same error.
- EODHD demo-token XAUUSD.FOREX intraday: HTTP 403, plain "Forbidden".
No account, paid key, broker API or real market orders used.

Gold API terms permit web application/commercial use; specific private Render
candle storage/algorithmic research rights, precise M15/H1/H4 finalization,
independent UTC market calendar, BID/ASK price basis, and history remain unverified.
Terms explicitly disclaim reliability and timely/uninterrupted service.

EODHD $29.99/mo is the strongest technically documented paid candidate:
XAUUSD real-time FOREX WebSocket supports BID/ASK quotes and private single-user
cloud research was confirmed to the account holder. Historical 1m XAUUSD.FOREX
is a separate indicative daily-delayed single OHLC series with undocumented
bid/ask/mid basis; it cannot be treated as matching WebSocket BID history.
Live-consistent Bid/Ask closed bars must be accumulated forward, with independent
session clocks, enough 50 H4 completed groups, no gaps and formal risk costs.

FXCM and Exness website onboarding currently reject residence in Lebanon;
do not suggest changing country or relying on their Demo endpoints. FXCM
ForexConnect remains technically documented but unavailable for this user.

This audit only hardens offline future-provider adapters; all final outputs
are WAIT, executable:false, no operational data was switched on.
