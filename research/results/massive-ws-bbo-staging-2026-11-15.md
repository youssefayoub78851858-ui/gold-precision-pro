# Massive XAUUSD WebSocket and historical BBO protocol rehearsal (2026-11-15)

Review branch only. **No live WebSocket, paid REST, API key, credential,
connection flag, vendor requests, Render deployment, broker orders or payments.**

Official vendor documentation:
- https://massive.com/docs/websocket/forex/quotes
- https://massive.com/knowledge-base/article/what-asset-classes-are-availalbe-through-massives-currencies-subscription
- https://massive.com/knowledge-base/article/how-can-i-connect-to-a-massive-websocket
- https://massive.com/knowledge-base/article/how-are-massives-forex-bars-built-and-what-do-v-and-n-mean-on-a-forex-bar

The REST ticker `C:XAUUSD` is **not** the WebSocket subscription
topic `C.XAU-USD`. WebSocket quote messages are `ev=C`,
`p=XAU/USD`, `a` (ask), `b` (bid), `t` (Unix ms), `x` exchange ID.
The network protocol requires CONNECT -> AUTH -> `auth_success` ->
SUBSCRIBE. A socket handshake cannot prove an active or entitled quote feed.

New private-offline protocol rehearsal:
`coordinator/massive_ws_standby.js`, tests
`coordinator/test_massive_ws_standby.js`.
Only accepts explicitly simulated messages via direct functions and
never implements transport. Crossed BID/ASK, stale/future quotes, reverse
time, quote gaps >90s, incomplete M15 and idle feed >3 minutes
fail closed. It builds completed M15, H1, H4 independent BID, ASK
and MID diagnostic OHLC, never trades.

**Corrected historical REST invariant:** Massive may return MULTIPLE
BBO quote observations at the exact same participant timestamp. Official
documentation explicitly displays two distinct quotes sharing a Unix-ns
timestamp. Historical adapter now accepts stable equal times in provider
order but rejects strictly reversed time; no fabricated deduplication.

The testing harness deliberately never asserts historical/live same-feed
equivalence, institutional feed entitlement, real session coverage, live
pricing or profitability. Both modules remain `WAIT`, `executable:false`.
The public dashboard remains an *unconnected source requirement checklist*
and does not surface any provider price. Confirm private licence and
actual BBO sample with Massive support before any further connection work.

No production branches, Render, or paid services modified.
