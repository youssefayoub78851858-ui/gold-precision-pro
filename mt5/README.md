# Local MT5 read-only candle bridge

This is an offline bridge prototype for a **desktop MT5 terminal** connected to
an already available broker symbol. It exports closed M15 bars plus one
current Bid/Ask snapshot to
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

The importer rejects bad symbols, mismatched epoch/UTC values, duplicates,
out-of-order rows, forming bars, invalid OHLC, and stale snapshots. It consumes
the raw `MqlRates.time` epoch as UTC and never subtracts the server's current
offset from historical bars. This avoids silently shifting old history when a
broker changes its DST offset. MQL5's Python integration documentation says
bar open times from the terminal are UTC; the exporter preserves raw epoch
seconds and the importer requires them to match the UTC string. It also stores
the latest `MqlTick.time_msc`, Bid, and Ask snapshot once per CSV row and rejects
stale, inverted, or inconsistent quotes. Still verify the exact broker symbol
and exported timestamps against an independently trusted clock before broader
research use. H1/H4 are aggregated from
complete UTC-aligned groups of M15 bars; gaps are not fabricated. MT5 tick
volume is kept distinct from exchange-wide GC volume.
The CSV ends with a count/time footer; the importer rejects missing or
mismatched footers, so a read taken during a file rewrite cannot be admitted as
a complete snapshot.

## Limits that keep it research-only

- This EA has not been compiled in MetaEditor or run against the user's broker;
  offline tests validate its source guards and the Python importer only.
- Broker symbol provenance, data-use rights, timestamp provenance, and
  first-availability timestamps are not authenticated by a CSV. The report
  therefore always sets `signal=WAIT`, `executable=false`, and
  `readyForTrading=false`.
- The CSV stores the raw timestamp epoch alongside its UTC rendering. The
  importer checks they match and does not infer the broker timezone. Do not
  reinterpret broker chart labels as UTC or add a fixed offset to history.
- No continuous Render upload exists. To put this feed on a phone, a future
  private transport, authenticated receiver, broker permission review, durable
  storage policy, and access controls must be completed first. Do not switch
  the demo or production service to this CSV as-is.
- This is a user-local connector candidate, not a free market-data licence or a
  proven, uninterrupted market feed. It needs a desktop/VPS terminal and the
  exact market symbol supplied by the broker.
