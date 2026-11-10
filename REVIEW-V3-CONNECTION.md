# V3 review connection and activation boundary

This branch is a review only. Do not change the existing public site's branch or GitHub Pages source. Do not enable Twelve Data or CUTOVER_MODE=live without approved shared quota handoff.

## Prepared connection

- `GET /review` on the repository's root Node server serves the review UI; `GET /review-ui.js` serves its controller. The review UI uses its own origin by default, never the old production host. An optional non-secret `gold-api-base` meta tag may select a separately approved review gateway; never put a broker token or provider key in HTML.
- The main button requests `/api/v3/research` once on demand. It shows WAIT with the returned reason, candles' close timestamps, and age. V3 research candidates are separate from executable signals. V3 currently always returns WAIT/executable=false by design.
- The root server delegates this route to the existing coordinator API. All candle requests use MARKET_DATA_BROKER_URL and BROKER_TOKEN. The root server and UI must never receive the provider key.
- Docker now copies all three V3 modules required by service/server.js. Previously standby could appear healthy while live startup would fail to load these modules.
- API admission rejects malformed, duplicate, future or unordered OHLC and wrong timeframe/symbol, uses the existing timing policy and the unchanged V3 frame checks. Invalid older H4 phase/alignment must be labelled INVALID instead of FRESH. Native candles are not silently realigned or fabricated.

## What standby does and does not do

`coordinator/entrypoint.py` is intentionally a provider-disabled standby listener. It does not start the broker, API or paper worker. Its authenticated V3 path returns HTTP 503, WAIT and STANDBY. No Twelve Data key is necessary. Internal bearer authentication is retained.

A Render Private Service is not reachable by a phone browser. The Node review gateway and the private broker are different roles; the gateway requires an explicitly approved public review deployment. Do not attempt to access the private hostname from GitHub Pages or send internal secrets from the browser. The existing public website remains on fix-analysis-v2 and still uses the provider directly; quota is NOT shared yet.

## Acceptance evidence

`test_v3_connection.py` tests the real root-to-API route against an isolated synthetic broker. `test_review_ui.js` tests the browser controller with deterministic stubbed responses. These are correctness tests, never profitability or live-feed evidence.

CI additionally builds the actual coordinator Dockerfile, imports V3 from the resulting image, starts it with no network or provider key, verifies standby under 512MB/0.5CPU and mounted local volume persistence after restart. This validates the image, not an actual Render disk or live provider quota.

A local trial using previously saved native XAUUSD OHLC and a historical clock correctly returned WAIT/INVALID because older H4 bars failed the unchanged V3 alignment check. No historical prices or provider data are added to the repository. That trial is not live, independent strategy validation, or profitability evidence.

## Next approved operational phase

1. Review CI result and approve a separate standby-only update of the existing private service, pinned to the reviewed commit. Preserve Oregon, 512MB/0.5CPU, 2GB /var/data, Auto Deploy off, CUTOVER_MODE=standby and provider key absent. Do not deploy automatically.
2. Confirm actual standby health/disk access through authorized Render access. Codex's current tools expose deployment metadata/logs, not a private HTTP/SSH session or secrets.
3. Before enabling provider use, reconcile the free 8 credits/minute and 800/day plan against current usage and every existing consumer, preserve the coordinator's stricter 7/60s and 720/UTC-day limits and persistent ledger, and obtain explicit live-data approval.
4. Approve a public review gateway/routing approach without silently changing the existing website or creating a paid subscription. Then schedule real closed M15/H1/H4 acceptance, including a genuine H4 close.

Rollback of a standby-only image update is the previous c9937a9 deployment with unchanged environment and disk. Never roll quota state back or delete its SQLite files. Any later live rollback must stop all consumers first and preserve usage accounting.
