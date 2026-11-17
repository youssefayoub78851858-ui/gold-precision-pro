# BiQuote review → private forward archive: staged, NOT activated

Branch: `review/v2-portable-tests-20261109`. **No production or paid changes.**
The forward holdout begins **2026-11-18T00:00:00Z**, not before.

The existing opt-in 24h review worker owns the sole polling loop (one group of
four fixed GETs every 120 seconds). With a separately authorized private sink,
the same received in-memory sample is archived into the protected Coordinator
volume using `biquote_private_forward_vault.ingest`. **There is no second poll.**

### Before operator activation on the confirmed private Coordinator workspace

1. Confirm the correct Render workspace and private service, a single worker,
   actual persistent disk mounted under `/var/data/`, permissions, costs and
   service branch. Do not activate on the free sleeping review dashboard.
2. Use existing review opt-in:
   `GPP_BIQUOTE_PUBLIC_24H_REVIEW=APPROVED_READONLY_NO_TRADING`
   and `GPP_BIQUOTE_REVIEW_START_UTC=2026-11-18T00:00:00Z`.
3. Separately authorize private archive:
   `GPP_BIQUOTE_PRIVATE_FORWARD_ARCHIVE=APPROVED_READONLY_PRIVATE_NO_TRADING`
   and set `GPP_BIQUOTE_FORWARD_VAULT_DIR` to a private folder on the
   already provisioned persistent disk, e.g.
   `/var/data/gold-live/biquote-forward`. Never use a temporary filesystem
   or publish the vault. Do not add secrets or market data to GitHub.
4. Verify metadata only from the authenticated monitor status:
   `biquotePrivateForwardVault.counts`, `quoteSamples`,
   `lastImportedUTC`, and safe 24h counters. An HTTP success alone does not
   prove a single candle was persisted; validate increasing *new* counts.
5. The window is bounded to 24 hours from its chosen UTC start; restarting
   with the same start never backfills missed calls. Another cycle or a
   continuous collector needs a separate explicit activation and quota review.

### Guardrails and limitations

- No registration, provider payment, browser credentials or broker keys.
- No extra network requests, trading access, orders, research admission or
  BUY/SELL; all decisions remain **WAIT**, `executable=false`.
- Structural check distinguishes unverified M15 constituent gaps from
  observed OHLC disagreements. A session gap is **never silently filled**.
- Requires fresh quote and closed, time-aligned source M15/H1/H4 candles.
  Stale, future, modified, duplicate, out-of-order or hash-damaged data cannot
  silently overwrite history. Quotes are isolated BID/ASK observations, **not**
  historical bid/ask OHLC candles.
- The vault includes actual provider prices; only sanitized counts/status are
  shown over monitor APIs and stdout. Owner-only storage is required.
- Upstream MT5 broker rights, broker session calendar, reliability, historical
  execution spreads, and strategy profitability remain **unverified**.
- Tests use synthetic fixtures and no live BiQuote network access. Deployment
  and actual file persistence on Render still require operator inspection.
