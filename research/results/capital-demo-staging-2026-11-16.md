# Gold Precision Pro Ultimate: Capital.com Demo standby research (16 November 2026)

## Decision: preferred candidate, NOT connected

Capital.com Support replied on 16 November 2026 that a Lebanon-resident Demo can obtain API access after identity verification and already enabled 2FA, with **no bank card, deposit, or API/market-data subscription charge**. They confirmed historical XAU/USD BID/ASK M15, H1 and H4 OHLC including August-October 2026. Each historical API response is capped at 1,000 bars, so larger ranges require separate bounded requests. See: https://open-api.capital.com/

**Unresolved:** Private Render.com cloud usage, candle storage/retention and personal paper/backtesting rights are being considered by a different Capital.com team. This cannot be presumed approved.

**Security:** Capital.com API keys are neither read-only nor Demo-only: every key can trade, and the same key works with Demo and Live bases. The company confirmed the Demo URL is https://demo-api-capital.backend-capital.com while the Live URL differs. This source stays offline until explicit user approval, a separate security review and confirmation of cloud/data rights. NO credentials are in GitHub. NO provider API requests or live trades are made.

Capital.com acknowledged historical response anomalies where some ASK candle components fall below BID. This offline adapter rejects such data, does not repair it, and never silently substitutes BID as actual ASK. Spread, brokerage fees, financing and broker-specific fills remain unverified for CFI or any live trading.

## Exactly what was added

- coordinator/capital_demo_offline_adapter.py: pure Python parser for already-supplied response dictionaries in the documented GET /api/v1/prices/{epic} shape (prices rows with snapshotTimeUTC and separate open/high/low/close BID and ASK values).
- Supports M15=MINUTE_15, H1=HOUR, H4=HOUR_4. Rejects malformed, unclosed, subsecond misaligned, invalid/nonfinite prices, inverted OHLC, crossed BID/ASK and contradictory duplicate history. Deduplicates exact page overlaps only. Flags unverified market/session gaps instead of fabricating candles.
- demo_price_get_blueprint returns a non-executing Demo-only, GET-only request description with maximum 1000 bars; there is no HTTP client and no authentication code.
- coordinator/test_capital_demo_offline_adapter.py has offline synthetic-only fixtures. GitHub CI runs the full negative and positive data-shape suite automatically.
- Every returned review status is WAIT; executable, researchEligible, paperTradingAllowed, dataRightsVerified, providerConnectionStarted, liveEndpointSupported and orderEndpointsSupported are always false. No production integration or buy/sell signal is introduced.

## Exact next gates before an actual data feed

1. Obtain written confirmation that authenticated one-user private Render research, candle storage and paper/backtesting are permitted, with any retention restrictions.
2. Only after that and explicit user agreement, decide whether to finish Capital identity verification. Never put any passwords, API keys, session tokens or trading-enabled credentials into chat, GitHub, screenshots or public UI.
3. Identify official Gold epic from the actual Demo markets lookup; do not guess a symbol from XAU/USD.
4. Validate real Demo BTC? NO — **XAU/USD only**: independent UTC timestamp opening convention, broker session calendar, pagination, historical warmup of at least 50 closed H4, M15/H1 consistency, BID/ASK integrity, rate limits, safe retry and actual quote age.
5. For any future live-data trial, design a separate Demo-only and GET-only process with hard hostname/path allowlists and independent credential isolation, not simply a conditional flag in an order-capable API library.
6. Paper trading remains disabled until reliable and permitted feed, cost model and independent tests are complete; actual trades always require separate explicit authorization.

No branch other than review/v2-portable-tests-20261109 is modified. No deployment, cutover, provider requests or subscription.
