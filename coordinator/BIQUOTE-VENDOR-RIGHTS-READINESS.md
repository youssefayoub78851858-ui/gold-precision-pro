# BiQuote XAUUSD vendor response — scope of permission and unresolved gates

Read-only recorded evidence, captured from the reply by **Halit, BiQuote
support@biquote.io, 2026-11-16** to the user's specific private
XAUUSD/Render inquiry. This is **not** a broker licence or regulatory opinion.

## Provider-confirmed for the user's proposed single-user private research

- BiQuote says continuous retrieval and private storage on Render,
  backtesting, private paper trading, and paper-only signal research are
  permitted under its published Terms, **without public redistribution**.
- BiQuote says quotes and M15/H1/H4 OHLC use the same single MetaTrader 5
  broker feed. Live-built OHLC comes from tick MID (bid+ask)/2; any initial
  empty series may have a one-time BID-based MT5-history seed. Support said
  the currently observed XAUUSD series are live-built MID.
- Support described approximately 192 retained M15 closed bars, 168 H1
  closed bars, and 180 H4 closed bars; longer data needs owner-side capture.
  H4 bars open at 00:00/04:00/08:00... UTC.
- Provider-declared trading window: Sunday 23:00 UTC to Friday 22:00 UTC,
  daily 22:00–23:00 UTC break, potentially shifting one hour around DST.
  No-tick hours produce no flat candles; missed live periods are not
  backfilled. Do NOT fabricate missing bars or silently assume the declared
  schedule holds for another broker.
- BiQuote quoted 15,000 requests per minute/IP, 50 concurrent connections,
  10 WebSockets, no API key or planned fee for this use; **no SLA**.
  Existing 720 slots x 4 GETs per 24h remains far below this ceiling.

## Explicit residual blockers

BiQuote says it knows of no upstream restriction specific to this private
use, but states it **cannot warrant the underlying broker's rights** on
that broker's behalf. Its permission covers the service relationship, not an
independent broker contract. Consequently:

1. `independentBrokerRightsVerified=false` and
   `brokerSessionCalendarVerified=false` must remain false.
2. OHLC is MID (possibly BID-seeded) and not broker-executable ASK/BID OHLC.
   Historical execution spread, fill, fees/slippage and lot contract are
   not yet independently verified.
3. GC, DXY, 2Y/10Y intraday, event/calendar, headlines and licensed
   trade-side Order Flow confirmation remains separately incomplete.
4. Private V3 technical watch is **not** a full BUY/SELL decision. The
   upper-level signal remains WAIT; `paperOrdersAllowed=false`,
   `executable=false`. Do not promote recorded data merely because the
   provider approves private *paper-only research*.

No payment, live order, production cutover, extra polling loop, or transfer
of the private candle/quote vault is authorized by this memo.

Reference: user-owned Gmail conversation “Re: BiQuote XAUUSD free API —
upstream rights, historical candle basis, private Render research”,
support@biquote.io, 16 November 2026. Terms supplied by BiQuote:
https://biquote.io/terms
