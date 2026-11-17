# Gold Precision Pro — private prospective BiQuote data vault (standby)

## What is ready
- **Repository:** review/v2-portable-tests-20261109 only. No production cutover.
- **Frozen future boundary:** **2026-11-18T00:00:00Z**, set before prospective data collection. Any earlier historical candles are ignored. This does **not** make the source or strategy independent by itself.
- **Raw market data must NEVER be committed to this public GitHub repository** or shown in public GitHub Actions artifacts/logs.
- **Private durable target:** existing Render private service \`gold-precision-coordinator\` has a 2GB mounted persistent disk at \`/var/data\` (inspected 2026-11-17). Intended vault: \`/var/data/gold-live/biquote-forward\`; owner-only 0700 directory, 0600 file. Free review web instance is **not** durable archival storage.
- **Module:** \`coordinator/biquote_private_forward_vault.py\` is pure ingest/storage, no HTTP/WebSocket, timers, recurring jobs, orders, trading engine, provider subscriptions or new secrets. Importing it is inert.
- **Protocol:** accept exactly one already-authorized, externally fetched snapshot containing \`source: "BiQuote"\`, \`quote\` and \`frames: {M15,H1,H4}\` with the original newest-first BiQuote OHLC envelopes. It validates UTC timestamp and closed grid, quote freshness under 30 seconds, BID <= ASK, observed MID parity if provided, sample and aggregate OHLC, duplicate/revision/late-bar rejection and current source staleness.
- **Storage:** append actual newly observed **closed** candles only; deduplicate exact duplicate timestamps; reject revised candles, malformed or out-of-order backfills instead of silently rewriting history. Keep source-open gaps and partial M15 coverage visibly unverified, without creating replacement bars. Maintain a limited quote BID/ASK observation series for descriptive spread statistics, **not** historical BID/ASK candle pairs or executable broker fills.
- **Integrity and privacy:** owner-only vault, no symlink file, atomic fsync + rename, SHA-256 stored-envelope checksum (detects accidental changes but is not cryptographic origin proof). The public metadata/status output does **not** print candle prices, raw BID/ASK or secrets. A checksum is not source authentication.
- **No eligibility:** every response remains \`WAIT\`, \`executable:false\`, \`tradeEligible:false\`, \`researchEligible:false\`, \`paperOrdersAllowed:false\`, even after successful ingestion. Existing V2/V3 signal engines unchanged.

## Activation requirements — NOT AUTOMATICALLY ENABLED
No market feeds have been newly connected by this change. No archival process is scheduled, and **zero real prospective bars are yet proven captured**. A future operator must validate private service ownership, continuing vendor permission, disk space/backup and the existing GET-only transport, and explicitly opt in to one isolated process that supplies snapshots to stdin at an approved modest cadence. Existing 24h metadata-only BiQuote observer remains unchanged. Do **not** run on the public free web service; do not upload market-price samples to GitHub.

CLI accepts a single already-acquired snapshot through private stdin **only**:
\`\`\`sh
GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE=APPROVED_READONLY_PRIVATE_NO_TRADING \
  python coordinator/biquote_private_forward_vault.py ingest \
  /var/data/gold-live/biquote-forward < /path/to/PRIVATE_OWNER_ONLY_snapshot.json
\`\`\`
The example source file must live privately on the coordinator's mounted disk, not in the repository. Never put credentials in stdin data or output. Do not enable any automated polling just because a vault exists. \`status\` accepts the same private directory and emits metadata-only totals.

## What still blocks a valid backtest
1. Historical source is MID, sometimes with an initial BID seed; no verified full historical ASK candle OHLC or real execution spread/slippage/commission model.
2. BiQuote's vendor support permits private research but has not warranted the unnamed underlying MT5 broker's rights. It has no independent broker session/holiday/DST certification, no provider SLA and no guaranteed missed-period backfill.
3. New forward rows are not an independent V3 performance test until the untouched strategy, timestamps, macro/news/GC/DXY/yield source entitlements and decision-time replay rules are frozen and independently assessed.
4. A recorded result must specify actual observed closed coverage, HTTP failures, unclassified market gaps, cross-timeframe parity and quote sampling frequency. Low-frequency quote samples **cannot** demonstrate spread at historical intrabar trade fills.

**Future observation only; no unverified trading or profitability claims.**
