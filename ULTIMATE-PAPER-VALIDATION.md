# Ultimate paper lifecycle and recorded validation batch

Review-only continuation of `09bc4ba6daa3d54982c7632a4bcafec3d383cb2e`.
No production, Render, MT5, Twelve Data or subscriptions were changed or enabled.

## Offline paper account

```sh
python coordinator/ultimate_paper.py /tmp/ultimate-paper.sqlite3 --replay coordinator/fixtures/ultimate-paper-synthetic.json
python coordinator/ultimate_paper.py /tmp/ultimate-paper.sqlite3
python coordinator/ultimate_paper.py /tmp/ultimate-paper.sqlite3 --kill
```

The example is **synthetic**, tests engineering behavior, and is not market performance. Use a separate database per immutable cost/risk configuration. Never store real account credentials in this database.

`ultimate_paper.py` evaluates Ultimate from the closed-bar snapshot, replacing user-supplied risk/equity with the persistent account state. The decision queues a paper entry on exactly the next M15 open. Missing next bars cancel pending entries. Entries are rejected when gaps invalidate stop/target geometry. One unique position and `BEGIN IMMEDIATE` serialization prevent concurrent or opposite entries. Replayed timestamps are idempotent; conflicting or reversed observations fail. Any evaluation or validation error rolls back the whole observation, events and balances together.

SQLite WAL persists configuration, balance, peak closed balance, kill switch, observation payload/digest, pending entry, open position, closed trades and ordered audit events across restart. UTC realized negative trades determine the daily loss allowance. Entry sizing rounds down to lot step, caps planned risk at 0.5% of current balance and remaining 2% daily allowance, and includes modeled exit slippage and round-trip commission. The ceilings are conservative functions of current balance, not a broker's start-of-day-equity rule. One active position reserves its risk by prohibiting additional entries. The kill switch cancels pending entries and prevents new ones; existing protective stops/targets still run. Gaps can exceed planned loss; the simulator does not promise loss containment.

**Execution convention:** recorded OHLC is BID. BUY enters at BID open + spread + adverse entry slippage, exits at BID. SELL enters at BID open - adverse slippage, exits against ASK OHLC (BID + spread). Stops fill at adverse opening quotes when gapped; known gap targets fill at their limit before later intrabar paths. Otherwise ambiguous candles use stop-first. All exits apply adverse slippage; round-trip commission is charged once on close. Intrabar exit times are conservatively recorded at bar close; no tick ordering is asserted. There is one final target per position, no partial scaling or broker orders. End-window open positions remain disclosed and unliquidated.

## Prepared data adapters, no transport

```sh
python coordinator/ultimate_connectors.py
```

`ultimate_connectors.py` accepts normalized JSON exports or CSV `layer,payload` rows for DXY, US02Y/DGS2, US10Y/DGS10, GC, calendar, headlines and trade-side Order Flow. It validates instrument, declared source/entitlement, UTC observation and availability, numeric values, and news publication timing. Replay selects only records available at the decision cutoff. The Ultimate evaluator also enforces recorded availability, instrument/entitlement and publication gates directly, so raw HTTP or paper snapshots cannot bypass them. Upcoming calendar events can be known in advance; future headlines cannot. Empty/missing feeds are not fabricated. FRED daily yields remain delayed context and will fail the existing five-minute intraday freshness gate when old.

FRED request templates are prepared as data, without credential loading or HTTP code. Commercial ICE/CME/news transport requires selecting a vendor and verifying actual entitlement later; no guessed endpoints or subscriptions are introduced. `research/results/connector-readiness.json` reports every adapter disabled, no network implementation and zero requests. Declared entitlement is not independent license verification.

## Recorded data and provenance

`research/recorded/manifest.json` pins every file hash, GitHub artifact digest, workflow run and commit, price convention, observed coverage, OHLC validation and gap counts. The downloaded ZIP hashes matched GitHub's artifact digests at import.

- September: artifact `13712631853`, run `42704406027`.
- October: artifact `13713792221`, run `42706196306`.
- Source declared by the original workflows: Dukascopy historical XAUUSD BID via dukascopy-node, with H1/H4 rebuilt only from complete M15 groups.
- 4,884 M15 candles total. Raw normalized archive members are committed for deterministic offline replay.

These are existing repository research artifacts, not independently attested provider or broker records. Hashes establish archive/file identity; they do not establish truth of market prices. Only existing archives were downloaded from GitHub; no request to a market-data provider was initiated and no market-provider quota was consumed in this batch.

## Historical and forward-window evaluation

```sh
python coordinator/ultimate_walkforward.py research/recorded/2026-09-bid.json research/recorded/2026-10-bid.json --output /tmp/ultimate-walkforward.json
# Optional licensed, locally recorded evidence exports:
# append --evidence /path/to/normalized-recorded-evidence.json
```

Both V2 (unchanged frozen EMA/RSI/ATR decisions) and Ultimate use the same persistent paper simulator and cost conventions. Signal generation sees only bars closed at each decision. It cannot enter using its decision bar's open. Snapshots warm up from earlier bars only. Account state, open positions and pending orders reset between reported windows to prevent cross-boundary trade leakage.

The chronological train/validation/test partitions use fixed 50%/25%/25% elapsed-calendar boundaries. Five expanding-history weekly forward windows begin after 21 calendar days. No parameters are fitted, optimized or selected from any outcomes. Each forward window discloses its past-history training interval. This is fixed-strategy walk-forward evaluation, not a learned-model training experiment. The overlapping overall partitions and weekly windows must not be pooled as independent observations.

Base costs: spread $0.40, adverse slippage $0.10 on each fill, $7 round-trip commission per lot, $100/point/lot. Stress: spread $0.80, slippage $0.30 per fill, $10 commission. Contract size, constant spread and fills are modeling assumptions, not broker-verified execution.

Committed result: `research/results/ultimate-walkforward.json`.

| Chronological window | V2 base trades | V2 base net USD | V2 stress trades | V2 stress net USD | Ultimate trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 31 | -88.41 | 31 | -312.12 | 0 |
| Validation | 24 | -412.33 | 24 | -440.32 | 0 |
| Test | 24 | +345.14 | 25 | +265.52 | 0 |

The first five weekly base-window PnLs are +62.56, -264.38, -183.69, -104.01, +254.24 USD. Different costs can change trade counts by changing stop timing and account risk. Reports include win rate, expectancy, profit factor, realized-balance drawdown, remaining open/pending positions, and exploratory IID bootstrap intervals only when at least 30 trades exist. These intervals do not account for serial dependence or establish statistical significance.

**No statistical success or trading readiness is established.** The test counts are small; September/October were already examined by earlier research and are not untouched holdouts. V2 loses in validation and several forward windows. Ultimate correctly remains blocked because these price archives contain none of the seven mandatory external evidence layers. Its zero trades are neither profit evidence nor a valid performance comparison. Realistically recorded cross-market/news/trade-side exports and new unseen periods remain necessary.

## Mobile review

Run `DEMO_MODE=standby PORT=3000 node server.js`, open `/ultimate`. Evidence results label synthetic/recorded status and explicitly deny live data. A second local file input displays paper account/trades reports without sending them to the server. `research/results/paper-synthetic-example.json` is labeled SYNTHETIC throughout. There are no automatic price requests or state-changing account endpoints.

Chromium was tested at 390×844: no horizontal overflow, explicit synthetic labels, evidence upload, local paper report display, and no automatic/API calls during local report import. Screenshot: `/tmp/gold-ultimate-mobile-batch2.png` (session artifact).

## Verification and remaining limitations

Tests cover next-bar entry, BUY/SELL quote conventions, stop-first ambiguity, gap targets/stops, daily loss reset/ceiling, restart/duplicate handling, concurrent observation serialization, conflicting replay, immutable configuration, kill switch, rollback and actual Ultimate evaluation with forged caller equity overridden. Connector tests cover disabled transport, entitlement checks, instrument validation, availability cutoff and publication leakage. Historical tests verify pinned files, reject digest tampering, and mutate future bars to check prefix invariance.

The account is an offline simulator, not a broker synchronization service. There is no live/paid feed, MT5 integration, partial target scaling, true depth/footprint, tick-level execution, variable bid/ask archive, calibrated CHoCH, or independent untouched-holdout proof. Original V2 package hashes and deployment setup remain unchanged.

Final local checks: **52 coordinator Python tests passed**; app suite **20 tests, 4 skipped**; **9 JavaScript scripts passed**; all **26 frozen package hashes matched**; mobile Chromium smoke passed. CI now also reruns the recorded comparison entirely offline. Local Python HTTP tests require the approved outer execution path because the inner sandbox denies localhost sockets.
