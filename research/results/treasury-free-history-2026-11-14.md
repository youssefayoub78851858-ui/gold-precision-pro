# Real, zero-cost U.S. Treasury daily yield history — 2026-11-14

One-time public GitHub Actions HTTP test:
https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/43621010545

Official endpoint:
https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=202611

Observed HTTP 200, XML, 14,578 bytes, nine daily rows for November 2026.
Every row has NEW_DATE, BC_2YEAR, BC_10YEAR among multiple columns.
First row: 2026-11-02, two-year 4.59%, ten-year 4.91%.

Implemented a strict zero-key monthly XML parser with duplicate/ordering,
invalid yield, future, stale, month selection, UTC clock and caching checks.
Mobile review-only route stays disabled until a separately authorized review
deployment and explicit TREASURY_DAILY_PUBLIC_FETCH_APPROVED=1 toggle.
No paid feed or broker operation, no production changes or real trades.

These are U.S. Treasury *daily* par yields, not intraday bond prices,
not US02Y/US10Y CFD prices, not ICE DXY and not trade timing.
The XML observation date does not prove release availability at the historical
minute, so point-in-time backtest authorization remains false.
Signal stays WAIT and executable=false in every path.

The minimum price for the entire Ultimate system remains unknown because
independently licensed XAUUSD real-time history and GC trades/DOM, real-time
ICE DXY and comprehensive geopolitical/consensus feeds remain unverified.
