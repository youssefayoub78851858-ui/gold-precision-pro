# Exness direct Trading API — new alternative (2026-11-14)

## Decision
Prefer evaluating Exness' **cloud-native read-only Info API key** over
a Windows MetaTrader VPS or FXCM native C++ for the next operator
entitlement step, *if* Exness confirms Info-key market data read scope and
account eligibility. No real key or account is configured.

Confirmed in a written Exness Support message (13 Nov 2026):
- Free MT5 Demo account, Investor/read-only password, no demo card/fee.
- Personal private research/backtesting with no public redistribution is
  allowed per support; VPS hosting is supported. This does **not** prove
  direct Trader API eligibility, free Windows VPS or Exness account availability.

Official docs:
- https://www.exness-api.com/trading/get-started
- https://www.exness-api.com/trading/get-started/recommended-integration-flow
- https://www.exness-api.com/reference/trading/get-candle-history
- https://www.exness-api.com/reference/trading/get-ws-ticks
- https://www.exness-api.com/authentication/request-signing
- https://get.exness.help/hc/en-us/articles/27866287512476-Exness-API
- https://get.exness.help/hc/en-us/articles/12856009514396-Exness-VPS-Setup-guide

Exness' dedicated Trader API differs from MT5 login: it needs an Exness
platform account, KYC and appropriate API credential. Eligibility, any
first deposit, metal availability in this account, read-only Info API key
market subscription permissions, personal Render use and costs are
UNVERIFIED. Exness free VPS has real account balance/volume and ongoing
trade eligibility, so is not a no-cost, demo-only cloud solution.

## What code exists
coordinator/exness_readonly_offline.js does NOT connect. It:
- Builds REST GET candle paths ONLY for XAUUSD/M15/H1/H4 and price_type=both
  (<=1000 bars per chunk, independent actual live account-specific limits).
- Signs GET metadata with caller-supplied temporary Ed25519 keys, no storage
  or network calls; all trading POST/DELETE endpoints are inaccessible.
- Validates Exness-documented dual-sided candle structures, closed UTC
  timestamps, Bid/Ask extrema, sufficient bars, M15->H1/H4 geometric parity
  and optionally a documented XAUUSD tick shape.
- Ignores any caller-supplied authorization; every result says WAIT,
  executable:false, paperOrdersAllowed:false, zero provider requests, and
  does not return raw prices or candles.

The comparison assumes mathematically exact aggregation in synthetic tests
and is *not* a market verification. Multi-session gaps, broker history/live
basis, quote rights and key permissions remain blocked. No paid actions,
trading activation, FXCM agreement, credentials or production changes.
