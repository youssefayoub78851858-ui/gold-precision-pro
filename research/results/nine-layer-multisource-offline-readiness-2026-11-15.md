# Nine-layer Gold Precision Pro Ultimate readiness — free pre-subscription build

2026-11-15. Review branch only, no production/Render deployment.

Added `coordinator/multi_source_readiness.py` as a **no-network,
non-trading research readiness summary**, composing existing isolated
Massive XAUUSD BBO and Databento GC MBO/MBP-10 synthetic fixture validators.

The nine required layers are:
XAUUSD_BBO, GC_TRADES, GC_DEPTH, DXY, US02Y, US10Y,
CALENDAR, HEADLINES, RISK_COSTS.

- XAUUSD input must be SYNTHETIC_TEST_ONLY and independently normalized
  via the strict local /v3/quotes-style BID/ASK candle adapter. No REST
  BID-OHLC substitute for historical BBO and no false H4 warmup.
- GC MBO and MBP-10 require correct schema, order/time and synthetic tag.
  GC full-depth is **not** the same thing as a single top-of-book quote.
- The H4 BID/ASK geometry and near-live GC observations are only
  *synthetic clock diagnostics*. Matching time alone is never data
  provenance, exchange aggressor-trade proof, continuity or source rights.
- US02Y/US10Y available via public official daily references **cannot**
  silently fill intraday interest rate verification.
- DXY licensed index, full USD calendar/actual-consensus, world-news
  coverage, and broker execution cost evidence are still missing.
- Output always `WAIT`, `executable:false`,
  `paperOrdersAllowed:false`, `verifiedLiveLayerCount:0`.
- No input flag, license claim or paid quote is promoted to genuine
  research by this review module.

Run locally `cd coordinator && python -m unittest -v test_multi_source_readiness`.
GitHub Actions also generates `/tmp/gpp-multi-source-readiness.json` with
the nine *unconnected* layers; it does **not** consume market or account data.

Future purchase decision requires licensed private Render single-user use,
historical BID/ASK XAUUSD and same-feed stream verification, CME GC
trades and depth permission, DXY licensed access, macro/news provenance,
broker costs and then an independently validated paper-trading period.

No subscriptions, credentials, vendor requests, real-market output,
AI accuracy or profitability is implied by these tests.
