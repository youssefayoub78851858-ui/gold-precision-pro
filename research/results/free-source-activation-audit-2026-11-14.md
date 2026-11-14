# Free-first source activation audit — 2026-11-14

## Results: **actual** one-time GitHub Actions public HTTP, no keys/payments
GitHub Action: https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/43618917778

- Federal Reserve H.15 DGS2: HTTP 200 XML; parser returned 2026-11-12, 4.86% (daily reference only).
- Federal Reserve H.15 DGS10: HTTP 200 XML; parser returned 2026-11-12, 5.10% (daily reference only).
- Federal Reserve monetary policy RSS: HTTP 200 XML, 6 recognized recent official headlines (partial coverage).
- BLS official economic release calendar: HTTP 200 text/calendar, 6 recognized scheduled events (no actual-vs-consensus).
- CFTC official Disaggregated Futures Only GOLD COMEX, code 088691: HTTP 200 JSON. Latest observation date 2026-11-03; managed-money net long-minus-short 103,614 contracts. Weekly lagged context, **not** real GC trades, DOM or delta.
- Gold API free /price/XAU: HTTP 200 JSON in earlier public one-time action 43613079168. Indicative spot snapshot only, not OHLC.
- Gold API no-key /ohlc and /history: HTTP 401 JSON. EODHD demo XAUUSD historical: HTTP 403 Forbidden. Not evidence of successful free OHLC access.

## What is free vs still not proved
Code already has: XAU/USD M15/H1/H4 offline technical model, mobile paper terminal,
Fed RSS, BLS calendar, Federal Reserve DGS2/DGS10 daily RSS, official-context view,
Gold API free display-only price, synthetic and recorded research, transaction journal.
New: independently validated CFTC GOLD weekly managed-money context and a one-off
real HTTP and parser audit (no account), guarded optional review-only mobile route.

Free sources DO NOT constitute licensed, timely, continuous XAUUSD BID/ASK OHLC,
ICE real-time DXY, GC real-time contract-specific trades/quotes, GC aggressor-side
Order Flow / Footprint / DOM, comprehensive geopolitical headlines, consensus-vs-actual
release surprises, or independently measured broker transaction costs.
CME public GC quotes are at least 10 minutes delayed and do not grant exchange
data redistribution or automated L2 access. CFTC weekly is not a substitute.

TradingView Essential is already owned, but a webhook may be used only in
accordance with TradingView's relevant conditions. It is NOT a blanket license to
export/build a private market-data feed via webhooks; no such ingestion was enabled.

## Operational decision
No paid subscriptions yet. All public and private trading decisions remain
WAIT, executable:false. Optional public CFTC fetching in the preview endpoint
requires CFTC_WEEKLY_PUBLIC_FETCH_APPROVED=1 and a *separately approved* private
review deploy; default is off. No Render deployment, env change, payment or
real broker trading was attempted.

Least expensive **verified complete system** price is unknown. Conditional
minimum for a genuine fresh XAUUSD indicative BID/ASK stream is EODHD personal
EOD+Intraday All World Extended at $29.99/mo, based on vendor email confirmation.
Its REST historical XAUUSD minute bars are daily-delayed with unknown BID/ASK
basis and do not constitute a matching authenticated bid/ask history. Additional
prices for ICE DXY and GC exchange trade/DOM entitlements and hosting remain to
be quantified before claiming full-system monthly cost.
