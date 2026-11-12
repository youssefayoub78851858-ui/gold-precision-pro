# Private EODHD monitor status — review-only staging

This changes only review-branch code; no Render deployment, provider request,
token, charge, cutover or execution. Existing standby remains default.

The coordinator's authenticated standby endpoint GET /api/v3/eodhd/readiness
uses the existing BROKER_TOKEN Bearer credential. It never reveals quote prices,
provider API tokens or full candles. It reads the previously staged adapter's
private file from DATA_DIR (normally /var/data/gold-live) and returns only its
status code, safe bar counts and age, WAIT and executable=false. It does not
claim the connector is live or that prices are licensed/trading-ready.
Absent/corrupt/insecure/stale/future snapshots are blocked or WAIT; even
apparently fresh samples remain WAIT_REVIEW_OBSERVATION_ONLY. HTTP responses
are no-store. Public review UI is not given this endpoint or access to licensed
prices.

No automatic startup of eodhd_ws_bridge.js was added; enabling the vendor
connector and deployment require separate explicit approval and paid entitlement.
No changes were made to main, backup-v1, fix-analysis-v2 or production.

Offline acceptance tests:
  cd coordinator
  python -m unittest -v test_eodhd_private_readiness
  node test_eodhd_ws_bridge.js
  python test_container_standby.py   # actual Docker offline network=none

For a future reviewed private deploy, /health remains the old exact standby
JSON, /api/v3/research returns WAIT/503, unauthorized readiness is HTTP 401.
