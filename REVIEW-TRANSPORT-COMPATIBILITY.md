# Review branch transport compatibility

This is a review-only preparation. The public Render service remains on `fix-analysis-v2` at deployed baseline `1ab1f331` and has not been changed. Its auto-deploy setting is currently enabled, so no commit is to be pushed to that branch as part of this preparation.

## Existing HTTP contract and review implementation

| Route | Existing success | Existing failure behavior | Review candidate |
| --- | --- | --- | --- |
| `GET /api/candles?interval=15min\|1h\|4h` | HTTP 200 with `{symbol, interval, source, values}` | Invalid interval: 400 `{error}`; missing data configuration: 503 `{error}`; provider error: 502 `{error, detail}`; transport failure: 502 `{error}` | Same public status and JSON keys; requests go to the shared broker with outputsize 2000. |
| `GET /api/candles?...&period=august\|older` | Same candle JSON; `end_date` is `2026-08-31` or `2026-09-30` | Same errors as the live candle route | Same date mapping and JSON contract; the broker cache distinguishes each native frame and date. |
| `GET /api/analyze` | HTTP 200 with `{symbol, marketStatus, dataStatus, signal, agreement, indicators, experimentalV2, warning}` | Missing configuration: 503 `{error}`; provider response error: 502 `{error, interval}`; insufficient data: 502 `{error, frame, count, invalidPrices}`; transport failure: 502 `{error}` | Restores the same response keys and nested indicator keys, while using the existing strategy module and broker transport. Stale data is explicitly forced to `WAIT`. |
| `POST /api/backtest` | HTTP 200 with the existing `backtest.js` result object | Invalid input: 400 `{error}`; other methods: 405 `{error}` | Uses the same root `backtest.js` and response contract; it makes no market-data request. |

The review V3 route `/api/v3/research` remains additional and research-only. On missing, invalid, or timed-out broker data it returns `WAIT` with `executable:false` or a clear unavailable response. No order execution was added.

## Transport and quota behavior

The public route implementation in `server.js` now talks only to `MARKET_DATA_BROKER_URL` and authenticates with `BROKER_TOKEN`; it has no Twelve Data URL or key reference. The coordinator broker owns provider access. Live and historical requests share its SQLite cache/lease key (`frame:end_date`), reserve one credit before provider I/O, and use existing safety ceilings of 7 per rolling 60 seconds, 720 per UTC day, and 200 history requests per UTC day. These tests use local synthetic candles and an injected provider; they do not contact Twelve Data or prove the user's current plan/quota.

## Preconditions for an approved cutover

1. Complete the account-wide inventory of every process using the Twelve Data key, including any consumer outside Render.
2. Confirm the durable quota database and handoff receipt on the private coordinator; retain the current manifest gates as false until each condition is evidenced.
3. Prepare and review the exact public transport commit on this branch. Preserve the current endpoints, response shapes, `index.html` consumer paths, and existing backtest behavior.
4. In an approved cutover window, first prevent new automatic deploys from the public production branch. Confirm one path is active at a time: all consumers must be broker-routed or stopped before the coordinator can fetch.
5. Drain at least 60 seconds after the last possible direct call, then perform the explicitly approved one-credit usage probe. Do not start market-data polling if usage, storage, routing, or minute-drain evidence is missing.
6. After activation is separately approved, verify a single request each for M15/H1/H4 through the broker, closed-bar freshness, matching API contracts, and V3 fail-closed behavior. Do not infer live readiness from synthetic tests.

## Rollback

Keep the public baseline deploy `dep-dbnq0q7b9u1s73cvqd0g` / commit `1ab1f331` available. If a cutover fails, pause the coordinator's live worker/provider access first, verify no broker consumer remains active, and only then restore the saved public deploy and its previous environment configuration. Never run the old direct Twelve Data path and live broker path concurrently. Preserve the coordinator disk and quota ledger; do not reset quota state during rollback.

## Verification in this branch

`coordinator/test_review_http_contract.py` exercises the public routes against an in-process broker with recorded synthetic candles and blocks any non-broker network destination. `coordinator/test_broker_quota_offline.py` tests the actual broker class for caching, restart persistence, cross-process leases, provider cooldown, and minute/day/history ceilings. These are compatibility and safety tests, not live-data or strategy-performance evidence.
