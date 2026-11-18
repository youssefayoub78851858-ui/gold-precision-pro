# BiQuote free XAUUSD one-shot follow-up — 18 November 2026

**Read-only, no paid provider calls, no credentials, no orders, no archiving.**

The GitHub Actions review job `44251654917` at commit `9388c25e`
performed one bounded run of **four credential-free public HTTP GETs** to
BiQuote for quote + M15 + H1 + H4. The output was reduced to an allowlisted
quality report, with no raw prices or candles in public logs.

- UTC run: 2026-11-18 06:29 (GitHub Actions job)
- Requests attempted: 4, retry count 0
- All four HTTP/JSON envelopes: OK
- Independent quote age: **3.01 seconds** (under the 30-second threshold)
- H1 fully supported M15 OHLC comparisons: **47**, **0 disagreements**
- H4 fully supported M15 OHLC comparisons: **9**, **0 disagreements**
- H4 inside-retention missing-M15 groups: **2**
- Their missing constituent M15 slots classified as **8** candidates inside
  the *vendor-described* daily pause and **0** outside the reference time
- H4 outer retention edge incomplete: **1**
- Impossible observed partial OHLC bounds: **0**
- Full structural acceptance: **false**
- Independent upstream broker rights and broker session calendar: **unverified**
- Trade / paper research admission: **false / WAIT**

The H4 gap *group count* 2 is not the same as the 8 individual constituent
M15 slots. This is a **single successful snapshot**, not a continuous
24/5 service-level or complete OHLC coverage test. The prior completed
Nov 16–17 24-hour test still reported 29 failed samples entirely in
the vendor-declared 22–23 UTC break, 0 structural audit passes and
independent maximum quote age of 183.859 seconds; the new one-shot
does not retroactively fix those observations.

## Practical free-path decision

No subscription is technically necessary to run a **bounded read-only
quote/closed-candle diagnostic** while BiQuote is online. However,
there is **no authorization to arm the forward archive** from this
one-time observation; automated paper orders and any real trade
remain blocked.

For the next go/no-go gate, establish independent underlying broker
schedule and rights (BiQuote support permits own private use under its
own terms but does not warrant upstream MT5 broker rights), then
validate several *new, market-open* independent quote-age and
closed-candle continuity windows with the already built failure-class
diagnostic. Treat reference-pause slots as explanatory flags, never
generate missing or flat candles. Test a durable post-holdout
private archive only after those guards and explicit authorization.

**GitHub evidence:** https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/44251654917

**No paid data usage, no Render Coordinator deploy, no production changes.**
