# FXCM source-integrity tightening — review-only, 2026-11-14

Prior commit 80683d9 passed the entire offline GitHub Actions workflow.
This change closes two additional candidate-feed loopholes in the
existing FXCM native intake contract:
1. A packet timestamp can be recent while the last actual M15/H1/H4
   candle is old. Now the validator rejects stale latest closed bars
   according to conservative, market-session-*unverified* ages.
2. A shorter H1/H4 history may have some valid M15 overlaps but silently
   omit a complete higher-frame group. Now every complete M15 block must
   have its corresponding H1/H4 candle, as well as matching Bid/Ask OHLC.

Any unexplained inter-bar gap blocks structural validity until the market
calendar is independently verified. Weekend or broker breaks are not
guessed. Synthetic test fixtures remain test-only, never live prices.

The validator remains entirely offline and only returns status metadata,
no raw prices, BUY/SELL or paper orders. Source licensing, broker account
permissions, UTC clock basis, SDK startup and data authenticity remain
unverified. No Render deploy, subscription or live trades.
