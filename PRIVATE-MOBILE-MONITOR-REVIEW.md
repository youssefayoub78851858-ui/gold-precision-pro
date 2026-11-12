# Private mobile monitor (review branch only)

The private coordinator serves a **static** phone-friendly HTML page at
\`/api/v3/monitor/dashboard\`. It contains no secrets or market data and may
load without authentication. It requires an existing strong \`BROKER_TOKEN\` typed
into the password field to call the **authenticated** private JSON endpoint
\`/api/v3/monitor/status\`.

- HTTPS required outside localhost; token kept only in JS memory while the
  page is open. No cookies, storage, URL parameters, redirect targets, or
  cross-origin requests.
- The protected status API uses only the existing offline EODHD private
  snapshot, zero new vendor requests, no trade signal and no account.
- It displays the reason codes and M15/H1/H4 counts only. These counts are not
  independent session/history verification. Never shows Bid/Ask or quote prices.
- Even a fresh snapshot is \`WAIT\`, \`executable:false\`,
  \`researchEligible:false\`, and the research engine is NOT_INVOKED.
- This screen does not itself poll continuously, persist alerts, or send push
  notifications. The separate offline journal module remains unstarted.
- Docker and HTTP authentication are smoke-tested using a network-isolated
  container on GitHub Actions. No Render deployment is performed.
- The production branch, protected branches, provider subscription, actual
  MT5 trade and \`CUTOVER_MODE=live\` remain unchanged.

Only after explicit authorization should this dashboard be deployed on the
PRIVATE review coordinator and its HTTPS, token policy, and isolation tested.
Never put \`BROKER_TOKEN\` into GitHub, screenshots or public URLs.
