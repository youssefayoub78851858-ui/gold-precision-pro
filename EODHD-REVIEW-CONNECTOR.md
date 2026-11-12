# EODHD XAUUSD WebSocket review connector

Not deployed, not activated, no subscription, no provider requests, no orders.

The EODHD support team confirmed that XAUUSD spot gold bid/ask is streamed
at wss://ws.eodhistoricaldata.com/ws/forex under their All World Extended plan.
The subscribe message is JSON with action=subscribe and symbols=XAUUSD.

This bridge uses the built-in Node 24 WebSocket, but does not run in the normal
coordinator startup. It is OFF unless both EODHD_CONNECT_APPROVED=1 and
EODHD_RIGHTS_APPROVED=1 are set, together with a paid EODHD_API_TOKEN in
the private host environment. Do not share a secret in chat or GitHub.

When explicitly enabled, the script writes a private, atomic status snapshot to
DATA_DIR/eodhd-private-review.json. Prices are indicative OTC bid/ask
midquote candles; never characterize them as actual broker OHLC or CME flow.
Only closed UTC M15 bars and complete H1/H4 aggregations are retained.
Disconnects, data gaps, reversed quotes, stale timestamps, and missing
authorization reset or quarantine bars. Research eligibility, signals and
execution ALWAYS remain false/WAIT. There is NO route from this review file
to the existing live strategy, REST UI, or paper worker.

Offline commands:
node coordinator/test_eodhd_ws_bridge.js
node coordinator/eodhd_ws_bridge.js
The second command prints DISABLED_NO_NETWORK without connecting.

Next: user approval for subscription, verification of paid XAUUSD frames,
private deployment approval, historical warmup/session calendar, clock checks,
and a separate reviewed feed-gate integration. Never set CUTOVER_MODE=live.
