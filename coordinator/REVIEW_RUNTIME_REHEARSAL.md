# Review runtime boundary — 27 November 2026

The separate Dockerfile.review-rehearsal is a CI-only Linux rehearsal.
It packages the actual M15 cycle, V3/r2, synthetic paper ledger and
mock connection tests without modifying the existing coordinator image
or creating any Render service. It runs without network, credentials,
or durable storage. A successful run does NOT establish live readiness.

## Remaining activation dependencies (not solved by a purchase alone)

- Capital.com Demo: private cloud data rights and isolated GET-only gateway.
  Massive is a fallback; the read-only probe is not a continuous real collector.
- Real historical/live BBO acquisition, independent session calendar,
  gap reconciliation, quote-to-candle production intake and real evidence.
- Official DXY or explicitly approved separate proxy strategy; real GC
  trades and depth, timestamped macro/news/calendar and actual cost evidence.
  Daily government yield references are not intraday observations.
- Dedicated private review runtime, verified persistent disk and offsite
  backup. Do not reuse the coordinator's existing vault disk. The new
  in-memory M15 paper rehearsal is not connected to the durable journal.
- Prospective validation of the frozen strategy on independent real data.
  No guaranteed number of entries or profit.

No automatic deployment, API activation, new subscription, or broker
order is permitted by this CI job. No production or main branch change.
