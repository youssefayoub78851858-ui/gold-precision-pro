# XAU/USD closed BBO spread-noise and mid-only breakout guard

Date: November 15, 2026. Review-only branch. This additional
`coordinator/xauusd_spread_noise_guard.js` diagnostic is hooked into
`/api/v3/ultimate/r2` under
`researchEnhancements.spreadNoise`, with an Arabic mobile summary.

It accepts only 21+ fully closed, contiguous 15-minute BID, ASK and MID
candle samples from a **SYNTHETIC_TEST_ONLY** offline fixture. It
rejects incomplete, future, stale, misaligned, crossed, malformed and
non-parity quote bases. Daily/broker session gaps require independent
session evidence rather than interpolation.

Spread at the synchronized **close** of each candle is ASK.close
minus BID.close. The guard compares the latest synchronized close
spread against the median prior 20 closed spreads; >3x triggers
a spread-widening warning. A candidate's 20-bar MID-close
breakout is only marked as a synthetic dual-basis observation if
BID and ASK closes BOTH exceed their corresponding 20-bar
historical extrema. Previous HIGH/LOW differences must never be
presented as same-timestamp bid-ask spread.

These thresholds are exploratory, **not calibrated** on market data.
The input is never passed to the frozen V3 strategy or promoted to
research/paper/executable eligibility. No provider requests, news,
broker connections, paid subscriptions, production deployment,
orders or claimed win rates.

All outputs remain WAIT/executable:false; absence of real licensed
BBO, verified broker session schedule, broker costs and independent
prospective validation still block live adoption.
