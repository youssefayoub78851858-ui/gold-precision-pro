# BiQuote forensic split — vendor-reference pause versus trading-time failures
**18 November 2026 — independent offline classification, never a source approval**

Source evidence: exact 24h Render Coordinator observation November 16, 19:45 UTC
to November 17, 19:45 UTC, previously recorded in
[BIQUOTE-24H-ACTUAL-20261117.md](BIQUOTE-24H-ACTUAL-20261117.md).
The deployed 24h worker predated per-endpoint failure classifications.

The existing Render historical log retrieval returned 29 unsuccessful
sample *timestamps*, in consecutive slots 69–97 from **22:03:02 to
22:59:02 UTC** on Monday November 16. The now-versioned offline
`biquote_declared_pause_forensics.py` checks 29 timestamp records
against the exact fixed 720-slot report and a **generic, vendor-declared
pause reference**. It neither retrieves more data nor makes a trading
decision.

| Evidence | Observed |
|---|---:|
| Total scheduled/sampled | 720 / 720 |
| HTTP/JSON all-four success | 691 |
| HTTP/JSON incomplete sample slots | 29 |
| Failed sample timestamps in reference 22–23 UTC pause | **29 / 29** |
| Failed samples in reference trading time | **0 / 29** |
| Fully verified source OHLC audits | **0 / 691** |
| Maximum independent quote age | **183.859 seconds** |
| Matched OHLC disagreements in fully M15-covered subsets | **0 in observed comparisons only** |
| Broker calendar independently attested | **No** |
| Feed cloud market-data rights independently attested | **No** |
| Paper/real signal eligibility | **WAIT; false** |

### What the distinction does and does not mean

The 29 failures were *recorded as unsuccessful all-four-HTTP/JSON
snapshots*, not 29 definitively missing quote HTTP requests. Their
alignment with BiQuote's stated market break helps avoid treating
them as randomly distributed downtime. It does **not** establish
the exact upstream MT5 broker identity, its DST/holiday session
calendar, or its data rights. It also does **not** prove HTTP success
or independent quote freshness during every trading minute.

The 2,051 H4 partial comparisons recorded in the historical worker
are repeated observations across retained windows; they are not
2,051 unique broken H4 bars. The 29 failure timestamps are
independent metadata from private Render logs; no client credentials,
prices, OHLC history, MID conversion or webhook payloads are
included in this document.

New offline test cases prove that even a single deliberately moved
failure from 22:59 into 23:01 UTC changes the classification to
unexplained. Missing, duplicated, out-of-range, off-cadence or
forged counters never return a reference-pause-only classification.

### Operational gate (unchanged)

- **Never** ignore missing market-open M15/H1/H4 data, stale or delayed
  quotes, price disagreements, or H4 partial groups; do not synthesize
  or backfill candles.
- BiQuote support provided consent for private Render retrieval and
  paper-only research under its own terms but cannot warrant upstream
  broker rights. Follow-up seeking the broker identity, schedule and
  COMEX distinction was sent in the original email thread.
- A single clean Nov 18 quote snapshot at 06:29 UTC had independent
  age 3.01 sec; it does not override a 24h maximum of 183.859 sec.
- The raw-data vault is not yet activated and has an immutable 10k
  quote-sample hard cap in the current implementation. It needs
  evidence-based capacity/retention decisions before future long-term
  collection.
- **No live orders; no automatic paper orders; no purchases; no
  source admission.** The review demo may show these static findings
  only as date-stamped research.

Offline regression:
`python -m unittest -v test_biquote_declared_pause_forensics`

GitHub Actions:
https://github.com/youssefayoub78851858-ui/gold-precision-pro/actions/runs/44258060383
