# Local MT5 read-only candle bridge

This is an offline bridge prototype for a **desktop MT5 terminal** connected to
an already available broker symbol. It exports only closed M15 bars to
`Common/Files/GoldPrecision/xauusd-m15.csv`; it does not transmit data, call a
vendor API, use credentials, or place trades. MT5's mobile app cannot host this
Expert Advisor. Keeping the terminal open on a PC or VPS is needed for repeated
exports; this repository does not create or rent a VPS.

## Local use

1. In desktop MetaEditor, compile `Experts/GoldPrecisionReadOnlyExport.mq5`.
2. Attach it to the exact broker XAU chart, e.g. the broker's `XAUUSD` symbol
   including any suffix. Set `InpConfirmedGoldSymbol` to exactly the chart name.
3. Leave `InpBarsToExport` at 2000 or lower. The EA calls `CopyRates` from shift
   1, which excludes MT5's currently forming candle. Its timer checks every 15
   seconds but rewrites the file only when a new closed M15 candle appears.
4. Read the snapshot locally from the terminal's shared `Common/Files` folder.
   Do not put raw price files into a public repository or public web service.
5. Validate it offline, after copying the file to a private local path:

   ```sh
   python coordinator/import_mt5_readonly.py /private/path/xauusd-m15.csv \
     --symbol XAUUSD.a --as-of-utc 2026-11-11T18:00:00Z \
     --output /private/path/mt5-review.json
   ```

The importer rejects bad symbols, timestamps, offsets, duplicates, out-of-order
rows, forming bars, invalid OHLC, and stale snapshots. H1/H4 are aggregated from
complete UTC-aligned groups of M15 bars; gaps are not fabricated. MT5 tick
volume is kept distinct from exchange-wide GC volume.

## Limits that keep it research-only

- This EA has not been compiled in MetaEditor or run against the user's broker;
  offline tests validate its source guards and the Python importer only.
- Broker symbol provenance, data-use rights, bar-offset history (including DST),
  and first-availability timestamps are not authenticated by a CSV. The report
  therefore always sets `signal=WAIT`, `executable=false`, and
  `readyForTrading=false`.
- The current server/UTC offset is written with the snapshot and applied to
  every exported historical row. A broker offset change within that history
  cannot be inferred safely from one offset. The importer reports
  `BROKER_UTC_OFFSET_HISTORY_UNVERIFIED`; resolve it from broker documentation
  or reject that file before evaluating timestamps.
- No continuous Render upload exists. To put this feed on a phone, a future
  private transport, authenticated receiver, broker permission review, durable
  storage policy, and access controls must be completed first. Do not switch
  the demo or production service to this CSV as-is.
- This is a user-local connector candidate, not a free market-data licence or a
  proven, uninterrupted market feed. It needs a desktop/VPS terminal and the
  exact market symbol supplied by the broker.
