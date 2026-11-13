# FXCM FCLite M15/H1/H4 in-memory staging — 2026-11-13

Continues the review-only branch from the first historical BID/ASK getter audit.
This is a software normalization test, **not** a real FXCM Demo connection.

- Verified with official FCLite documentation that historical responses expose
  bid and ask bar fields, getDate, getCount and isBar; Node is documented.
- The improved offline normalizer accepts UTC ISO Z values and JavaScript Date
  objects without translating broker timezones; refuses local/unzoned strings.
- Individual response checks reject tick-mode results, crossed prices,
  malformed OHLC, duplicate times, and incomplete candles.
- The three-frame staging gate independently checks M15/H1/H4 BID and ASK
  aggregations; rejects inconsistent prices and partial or missing
  higher-timeframe bars. It never manufactures missing candles.
- The returned frames are labeled UNVERIFIED and **quarantined**.
  Research, paper, execution and any real order stay forbidden and the
  provider remains disconnected. 50-bar geometric warmup does not prove a
  market session calendar or legal rights.
- No SDK installation, credential fetch, login, data request, payment, Render
  deployment or modification of production branches.
- Remaining blockers: vendor package compatibility/runtime, FXCM EULA/cloud
  permission and read-only demo access, authentic UTC timing/closed-bar
  semantics, XAU/USD bid/ask live vs history parity, and complete sessions.

Reference: https://www.fxcm.com/public-docs/fclite/trading/prices/get_historical_prices_for_an_instrument.html
Reference: https://www.fxcm.com/public-docs/fclite/installation/downloadandinstall.html
