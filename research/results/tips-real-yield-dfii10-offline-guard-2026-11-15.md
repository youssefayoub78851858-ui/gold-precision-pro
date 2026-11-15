# DFII10 daily real-yield readiness and macro-surprise leakage hardening

Date: 2026-11-15. **Review branch only**.

Added `coordinator/official_dfii10_daily_review.js` for LOCAL FRED
DFII10 CSV (Federal Reserve H.15 inflation-indexed 10-year constant-maturity
yield), plus tests. It never calls a provider, reads credentials, or places
orders. It accepts only explicitly labelled SYNTHETIC_TEST_ONLY or
LOCAL_RECORDED_UNVERIFIED data and requires a UTC receipt at or before the
review clock; a receipt DOES NOT prove first dissemination time.

A daily real-yield CSV may contain `.` (missing/non-trading days); skip
those dates without fake interpolation. Reject duplicates, out-of-order
dates, implausible or nonfinite yields, future observations, unsupported
headers, stale files and future receipts. Output includes the latest
DFII10 percent and previous valid observed date/change as a **daily-only
reference**, always `WAIT`, `executable:false`,
`pointInTimeBacktestEligible:false`. It cannot feed V3 or paper orders.

Optional nominal comparison requires the existing separate H.15 DGS10
review to be marked official refreshed on the SAME observation date;
stale stored fallbacks and mismatches are rejected. Nominal minus TIPS
is an approximate daily breakeven measure, not intraday confirmation
or causal proof of gold direction. Vendor rights, revision
history and first availability are not validated.

Also hardened synthetic-only economic surprise diagnostics:
- reject a release timestamp earlier than its scheduled time (no
  premature leak disguised as a valid surprise);
- keep relative surprise `null` for near-zero consensus rather than
  generating absurd percentages;
- reject subtraction overflow; always no trading vote.

Public source description: https://fred.stlouisfed.org/series/DFII10
The official H.15/FRED series is DAILY and may be revised; inspect data
rights before uploading or redistributing third-party files.
No live data, production, Render, subscriptions or account settings changed.
