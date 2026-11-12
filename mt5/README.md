# Local MT5 read-only candle bridge

This is an offline bridge prototype for a **desktop MT5 terminal** connected to
an already available broker symbol. It exports closed M15 bars plus one
current Bid/Ask snapshot to
`Common/Files/GoldPrecision/xauusd-m15.csv`; it does not transmit data, call a
vendor API, use credentials, or place trades. It refuses to export unless the
connected MT5 account reports `ACCOUNT_TRADE_MODE_DEMO`, and stamps that mode
in the CSV for the importer to verify. MT5's mobile app cannot host this Expert
Advisor. Keeping the terminal open on a PC or VPS is needed for repeated
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

The importer rejects bad symbols, mismatched epoch/candidate-time strings,
duplicates, out-of-order rows, forming bars, invalid OHLC, and stale snapshots.
It deliberately treats the `MqlRates.time` and `MqlTick.time_msc` epoch values
as unverified candidates. The Python integration docs explicitly say its
returned bar/tick times are UTC, but native MQL5 references describe these
fields as period/price update times without explicitly assigning UTC. Matching
an epoch to a UTC-formatted string only proves the formatting is self-consistent;
it does not verify the source clock basis. `TimeCurrent` is server-formed,
`TimeGMT` depends on local OS DST configuration, and `TimeTradeServer` is
computed by the terminal. The exporter records all three diagnostic clocks
without using their offsets to rewrite historical timestamps. The importer
therefore emits `CLOCK_BASIS_UNVERIFIED`, `WAIT`, and no admissible frames until
an independent live clock/DST diagnostic is run.

The offline diagnostic accepts two actual local MT5 Demo CSV captures, one on
each side of a broker-documented DST transition, and an independent UTC time
recorded at each capture:

```sh
python coordinator/mt5_clock_diagnostic.py \
  --sample before_transition /private/path/before.csv "$TRUSTED_UTC_BEFORE" \
  --sample after_transition /private/path/after.csv "$TRUSTED_UTC_AFTER" \
  --trusted-clock-source "independent UTC clock reference" \
  --expected-server-shift-seconds "$CFI_SIGNED_DST_SHIFT_SECONDS" \
  --output /private/path/clock-diagnostic.json
```

Capture both files from a running Demo terminal on either side of an actual
broker DST transition, with an actively updating quote. Record an independent
UTC timestamp at each capture; the diagnostic checks the raw tick epoch and
`TimeGMT()` against it, and requires the newest closed M15 epoch to equal the
last closed quarter-hour implied by that UTC timestamp. Use the exact transition
and signed server shift documented by CFI; the diagnostic does not assume a
broker timezone or a one-hour shift. A unit-fixture pass only tests the
diagnostic code. The tool has no network access and never unlocks research or
trading by itself. H1/H4 are candidate aggregates
from
complete UTC-aligned groups of M15 bars; gaps are not fabricated. MT5 tick
volume is kept distinct from exchange-wide GC volume.
The CSV ends with a count/time footer; the importer rejects missing or
mismatched footers, so a read taken during a file rewrite cannot be admitted as
a complete snapshot.

## Limits that keep it research-only

- This EA has not been compiled in MetaEditor or run against the user's broker;
  offline tests validate its source guards and the Python importer only.
- The existing EA is a read-only exporter, not an order executor. The MT5
  importer currently keeps every frame out of the research engine and emits
  `WAIT` while clock basis and data rights are unverified. Wiring an order
  sender to the paper engine now would bypass those gates, so no demo-order EA
  or Demo-to-paper route is enabled.
- Broker symbol provenance, data-use rights, timestamp provenance, and
  first-availability timestamps are not authenticated by a CSV. The report
  therefore always sets `signal=WAIT`, `executable=false`, and
  `readyForTrading=false`.
- The importer stores candidate frames separately and leaves its admissible
  `frames` empty until clock-basis evidence exists. A diagnostic result covers
  only the sampled DST window; it does not authenticate the data licence,
  broker symbol, or all historical timestamps.
- No continuous Render upload exists. To put this feed on a phone, a future
  private transport, authenticated receiver, broker permission review, durable
  storage policy, and access controls must be completed first. Do not switch
  the demo or production service to this CSV as-is.
- Official references: [MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates),
  [MqlTick](https://www.mql5.com/en/docs/constants/structures/mqltick),
  [TimeCurrent](https://www.mql5.com/en/docs/dateandtime/timecurrent),
  [TimeGMT](https://www.mql5.com/en/docs/dateandtime/timegmt),
  [TimeTradeServer](https://www.mql5.com/en/docs/dateandtime/timetradeserver),
  and the separate [Python CopyRates UTC note](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py).
- This is a user-local connector candidate, not a free market-data licence or a
  proven, uninterrupted market feed. It needs a desktop/VPS terminal and the
  exact market symbol supplied by the broker.
