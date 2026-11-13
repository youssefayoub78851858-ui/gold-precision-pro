# FXCM FCLite isolated Linux npm availability check (2026-11-13)

This is a probe of a public npm package, not FXCM login/market data,
cloud entitlement or a live research feed.

- Official FCLite instructions list @gehtsoft/forex-connect-lite-node,
  configured via the vendor's MyGet scoped npm registry.
- On the assistant's local Linux runtime, npm installation failed at DNS
  resolution for www.myget.org (EAI_AGAIN). This is inconclusive about
  provider availability because this runtime has restricted internet access.
- A separate GitHub-hosted Linux job installs in an isolated temp directory,
  configures the documented scope registry, sets --ignore-scripts,
  --no-audit, --no-fund, --no-save, no stored npm credentials,
  sets no broker credentials, and times out.
- Reads only the installed package's package.json to identify name,
  version, and Node engine requirements. Does not import SDK files or call
  FXCM, and does not alter the production Docker image.
- Job creates fxcm-fclite-package-probe JSON artifact:
  INSTALLED_NO_SCRIPTS is package retrieval only; not proof that
  imports/authentication/candles/safety work. BLOCKED_NOT_VERIFIED
  preserves failure details without interpreting DNS as vendor closure.
- This job reports a blocked discovery as completed, not a successful SDK
  install. Never flip WAIT, permission gates, or production settings.

No account, payment, order, real market request, API key, deployment,
new Render service, or live provider entitlement is authorized.

Official install: https://www.fxcm.com/public-docs/fclite/installation/downloadandinstall.html
