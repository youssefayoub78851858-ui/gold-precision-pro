# Research-only paper admission — data not yet licensed

This review-only addition is a conservative precheck attached to
`/api/v3/monitor/status`, visible on the authenticated mobile monitoring page.
It is not an order system, does not instantiate a PaperAccount, and does not
fetch or invent market data.

Until a separately verified feed with session history and written rights,
completed broker-cost/risk evaluation, and explicit paper activation are in
place, it returns `BLOCKED`, `WAIT`, `paperOrdersAllowed:false`,
`paperRunning:false`, and `ledgerCreatedByGate:false`. It does this even
if someone forges a BUY signal or inserts 50+ fake closed bars.

Missing/late audit heartbeat, insufficient M15/H1/H4 closed candles, missing
licensing, and unverified paper costs are displayed as short allowlisted reason
codes only. Public proxy strips unexpected or unsafe fields; no balances,
quotes, provider tokens, or private trade history are forwarded.

The existing `ultimate_paper.py` supports offline synthetic/recorded replay
with its own risk limits. That simulator has NOT been connected to the Render
monitor, and there are NO live or simulated positions being opened on Render.

No subscriptions, provider calls, live trading, alert deliveries or production
changes are authorized by this code. Deploy to the two review services ONLY
after GitHub Actions completes successfully.
