# Multi-source data preparation — 2026-11-15

Added a **source-specific historical XAUUSD BBO fixture adapter** for Massive
`C:XAUUSD` `/v3/quotes` field shapes: `bid_price`, `ask_price`,
`participant_timestamp` (Unix nanoseconds). Unlike forex BID-derived
aggregate OHLC bars, this adapter reconstructs independent BID/ASK and
derived MID closed candles on M15/H1/H4 in a source-neutral frame layout.

- Never interpolate a missing M15 interval or blindly carry quotes over
  disconnected periods. UTC-aligned full M15 requires coverage from within
  60s of interval opening to within 60s of interval close, and no quote
  silence above 90s in the synthetic fixture. H1 and H4 require all 4/16 M15.
- A benchmark synthetic 800-M15 history separated by a 48-hour assumed
  session closure must yield 200 H1 and 50 H4, **without** recognizing the
  closure as independently verified.
- Removing an intermediate quote causes one M15 to be rejected, thus only
  199 H1 and 49 H4 are complete.
- This is NOT a live source connector. It cannot fetch external data,
  read keys, represent a provider entitlement, claim a valid independent
  calendar, prove same-feed WebSocket parity, license paid data on Render,
  or enable research/trading. Output WAIT, executable:false always.
- Quote activity is not exchange-traded volume; this source cannot replace
  Databento GC trades, aggressor delta or level-2 DOM.

Planned layers and source responsibilities:
1. XAUUSD historical/stream BBO: Massive; private authenticated rights,
   50+ verified H4, time continuity and same-feed provenance still pending.
2. GC live futures trades + MBO/MBP: Databento; separate paid plan,
   contract mapping, exchange entitlement and actual live sample still pending.
3. DXY: ICE or alternative licensed intraday index, unconnected.
4. US02Y/US10Y: free US Treasury/Fed daily context, not intraday yield.
5. Calendar, consensus, geopolitical news: independent licensed sources
   pending; official releases alone cannot substitute for complete coverage.

Next step before any purchase: acquire vendor confirmation/sample proving
historical quotes for XAUUSD, timestamp/retention eligibility, **private
single-user Render access**, and real-time same-source continuity. Paid
XAUUSD and GC vendor clients remain disabled.

No Render deployment, production mutation, payments or broker orders.
