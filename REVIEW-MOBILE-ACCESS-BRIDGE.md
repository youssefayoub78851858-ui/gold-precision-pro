# Private monitoring mobile access - prepared, NOT activated

After deploying the review-demo branch, the page path is
https://gold-precision-v3-review-demo.onrender.com/private-monitor

For user safety the relay is DISABLED by default, and works ONLY when:
- public REVIEW-DEMO service sets DEMO_MODE=standby and PRIVATE_MONITOR_PROXY_APPROVED=1
- private coordinator sets a strong MONITOR_READONLY_TOKEN 32+ characters,
  distinct from BROKER_TOKEN
- both services deploy this reviewed commit and private network access works

The public relay sends ONLY X-Monitor-Viewer to the fixed Render private-service
host: gold-precision-coordinator:3110. No BROKER_TOKEN on the public review
service. It accepts only research WAIT summaries, reason codes and candle counts;
no prices, account identifiers, secrets or real trade signals.
Tokens must be set in private Render environment settings, not in GitHub,
a screenshot, a chat message or the mobile URL. Browser keeps the viewer token
in page memory only and requires HTTPS.

Do not deploy or activate with real data until explicit review. Production
is untouched, and no EODHD subscription, MT5 execution or paper account starts.
