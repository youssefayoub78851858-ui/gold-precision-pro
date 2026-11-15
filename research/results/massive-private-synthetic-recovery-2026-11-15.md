# Massive private synthetic history recovery (2026-11-15)

* Review branch only. No broker/quote vendor calls, subscriptions, payments,
  public-market display, production or Render modifications.
* Added `massive_private_closed_store.js` and unit tests for storage of
  **SYNTHETIC CLOSED M15 BID/ASK/MID only**. It never saves the latest quote,
  an open candle, authentication, WebSocket state, API keys or "ready" flags.
* Before saving and after loading, validate UTC-aligned closed M15, strict
  ascending timestamps, positive OHLC, bid/ask constraints, consistent
  midquote, independently reconstructed H1/H4. Reject future or malformed
  prices and attempts to assert real-market entitlement.
* Writes only in explicit local owner-only (0700) folder, atomic private
  file (0600), refuses symlinks/wrong-owner/wrong permissions and tampered
  integrity digest. The digest detects accidental changes, **not** proof of
  external data ownership or cryptographic market-feed provenance.
* Cold restore starts a fresh disconnected MassiveQuoteStandby with
  preserved synthetic *closed* bars. It cannot restore an old tradable quote
  or any provider authorization. Results always WAIT; no paper orders.
* Existing production and preview Render deploys are unchanged. Storage
  persistence for actual licensed data would need a separately approved
  private storage plan and a rights/retention review, not this test fixture.

Remaining blockers before provider activation: historical BID/ASK entitlement
and same-feed overlap, private cloud use & deletion rights, live XAUUSD
coverage, licensed GC trade/depth, DXY, news/calendar quality and approved
broker paper-cost accounting.
