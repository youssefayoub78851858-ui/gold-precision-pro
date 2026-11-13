# FXCM FCLite Node alternative — source and integration preflight (2026-11-13)

## New evidence
- FXCM's official FCLite Node/JavaScript API documentation is a separate, potentially
  more portable candidate than **legacy Python forexconnect wheels (cp35–cp37)**.
- Official SDK installation docs list \`@gehtsoft/forex-connect-lite-node\` and a
  vendor-managed npm registry at \`https://www.myget.org/F/gehtsoft-public/npm/\`.
  This is **documentation only**; no package was downloaded or installed.
- FXCM's historical-price example explicitly exposes separate \`getBidOpen\`,
  \`getBidHigh\`, \`getBidLow\`, \`getBidClose\` and corresponding ASK getters.
  This is an API *shape*, not proof that XAU/USD Demo returns usable closed bars.
- Official demo and streaming support are documented. The FXCM provider follow-up
  about Debian Bookworm, modern runtime, read-only credentials, and cloud rights
  was already sent; do **not** repeat it without new evidence.

## Implemented now
\`coordinator/fxcm_fclite_history_audit.js\` validates an **in-memory**
synthetic response matching the documented historical getter shape. Tests cover
crossed BID/ASK, invalid price, unclosed and non-UTC candles, missing getters,
wrong instrument, and forged provider approvals. The function **always** returns
\`WAIT\`, \`executable:false\`, and \`paperOrdersAllowed:false\`.

## Blockers before actual FXCM use
1. Written FXCM EULA and explicit permission for the private cloud read-only
   project; EULA acceptance is a user action, not inferred here.
2. Verified FXCM Demo eligibility, a **read-only account** or independently
   isolated trading-disabled credential, and actual XAU/USD symbol.
3. Documented and measured FCLite Node package runtime on current Debian
   Bookworm/Node base; package registry reachability/version/licensing.
4. Genuine closed M15/H1/H4 ASK and BID historical data, UTC/session calendar,
   backfill, quote timestamps, zero gaps, broker-side spread/price parity.
5. Authorized private staging run, with broker data/keys never in GitHub.
   
No demo login, market-data request, package install, account change,
paid service, Render deployment, or live/paper order executed in this step.
Production/main/backup branches untouched.

References:
- https://www.fxcm.com/public-docs/fclite/
- https://www.fxcm.com/public-docs/fclite/installation/downloadandinstall.html
- https://www.fxcm.com/public-docs/fclite/trading/prices/get_historical_prices_for_an_instrument.html
- https://www.fxcm.com/markets/algorithmic-trading/compare-api/
