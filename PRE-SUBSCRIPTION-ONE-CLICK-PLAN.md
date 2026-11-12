# Gold Precision Pro Ultimate — one offline run, five controlled activation gates

No new subscription, API request, paid data, cutover, trading, or production deployment.

**One click on mobile:** GitHub Actions > V2 offline unit tests > Run workflow >
select review/v2-portable-tests-20261109. The workflow already performs the full
offline test suite. The new final artifact pre-subscription-readiness contains
machine-readable status for each of five stages. Green offline checks DO NOT
mean the real market has been tested.

1. Private Render runtime: code and offline Docker standby tests exist. An
   actual private deploy and HTTP verification still require separate approval.
2. XAUUSD EODHD: WebSocket client and security gates exist. The client is OFF;
   subscription, real token and licensing verification are still required.
   Its current midquote bars cannot silently be treated as broker BID fills.
   Closed-bar history, session calendars, clock and vendor compatibility
   need genuine live validation.
3. News/macro/GC: Federal Reserve/BLS free reference code and news classifiers
   exist, but comprehensive geopolitical news, current DXY, live GC order flow,
   licensing and timestamps are not yet connected or validated.
4. Paper monitoring: engine and offline simulation exist, but no validated
   always-on live paper run or complete transport/notification layer.
5. MT5 Demo: read-only exporter is demo-restricted, but MetaEditor compilation,
   Windows capture and independent UTC/DST verification are outstanding.

A paid data subscription by itself does NOT instantly enable all five stages.
Each new provider must pass quality, authorization and cost checks. Keep
WAIT and executable:false until separately approved. main, backup-v1,
fix-analysis-v2, production and CUTOVER_MODE=live must stay unchanged.

Local offline report:
    python coordinator/pre_subscription_preflight.py --output /tmp/pre-subscription-readiness.json

This checks source-file guards only; tests and actual service validation are separate.
