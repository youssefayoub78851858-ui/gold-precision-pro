# Gold Precision Pro Ultimate — continuation brief (2026-11-20)

## Standing user directive
Continue work in an integrated batch, in sequence, without pausing for approval after every file or stage. Complete all feasible code, offline tests and evidence review before producing a concise final report. Do not restart the project from scratch.

## Mandatory boundaries
- Repository: `youssefayoub78851858-ui/gold-precision-pro`
- Writable branch ONLY: `review/v2-portable-tests-20261109`
- Leave `main`, `backup-v1`, production Render and live cutover unchanged.
- No payments, subscriptions, paid API calls, new persistent collection, or infrastructure charges without specific prior authorization.
- No real orders, no automatic paper orders, no synthetic data presented as real prices. Keep `signal=WAIT` and `executable=false` until independent source, execution and forward-performance conditions are proven and separately authorized.
- Do not expose private feed prices, source keys, credentials or user identifying information in public GitHub files.

## Current development evidence (not a trade-ready result)
- At the 2026-11-20 review, four-stage offline GitHub CI passed on commit `8825e6b5`.
- The review dashboard offline safety test was corrected and passed on commit `733bacbb`.
- New `coordinator/biquote_pre_signal_milestones.js` plus unit test and four-stage workflow: local H4 count milestones, no trades or private prices.
- Historical observed H4 count and accepted snapshots must be queried from actual authenticated latest storage before representing them as current; past summaries alone are not live evidence.
- BiQuote's 2026-11-16 email states private single-user Render storage and paper research are permitted under its own terms, with broker-MT5 mid-built candles and possible bid-based seed, and daily/weekly breaks; the company explicitly cannot independently warrant upstream broker data rights. A follow-up asked for the broker name, exact session and COMEX-vs-CFD clarification; no response verified as of the 2026-11-20 review.
- Macro / DXY / US yields / GC order flow synchronization, validated bid/ask execution costs, sufficient independently verified time-aware H4 history and forward after-cost holdout results remain unresolved.
- The 21-contiguous-H4 technical and 50-H4 paper-history milestones are existing research checks, **not** proof of profitability or real recommendation eligibility.

## Next autonomous sequence
1. Verify latest review branch HEAD and CI status, and fix failures only on allowed branch.
2. Validate upstream source permission and session/price-basis claims; do not infer it from vendor permission alone.
3. Verify prospective closed M15/H1/H4 candles and point-in-time receipt, gaps and broker breaks; never backfill fabricated bars.
4. Reconcile multi-source context and execution-cost evidence using authorized sources only.
5. Execute independent prospective paper holdout analysis when real sufficient data exists; retain fail-closed WAIT otherwise.
6. Report exact changed commits, successful/pending tests, external blockers and whether a real BUY/SELL recommendation is independently justified. No promise of profit.

This file is a portable GitHub handoff, not a ChatGPT saved-memory entry.

## 2026-11-20 next batch — evidence and paper validation

- **Review-only changes**: strengthened `biquote_pre_signal_milestones.js`
  to reject impossible UTC dates, frame-count and receipt contradictions,
  stale/missing M15/H1/H4 expected slots, unverified 21-H4 warmup parity,
  and ledger counters from a different decision cycle. The related
  fail-closed test suite passed in four-stage CI on `e7197104`.
- Added `prospective_paper_holdout_audit.js` and its test. This is an
  **offline, untrusted, sanitized arithmetic auditor** for closed paper
  outcomes, net of supplied spread/slippage/commission assumptions.
  It checks chronological decision/entry/exit/first-seen timestamps and
  computes net PnL, R expectancy and realized drawdown. Even a sample
  with more than 30 profitable outcomes **never** grants a real or
  paper execution permission, source-licensing attestation, independent
  statistical proof, or a BUY/SELL recommendation.
- The paper-auditor regression was corrected after a test-case mistake
  (a purported invalid decision timestamp actually preceded the entry).
  Four-stage offline GitHub Actions PASSED on commit `7e627ce3`,
  run `44631804890`. Later changes should verify their own CI separately.
- Read-only Render coordinator metadata from **2026-11-19 21:46 UTC**:
  stored closed M15=179, H1=44, H4=11; strict contiguous tails
  M15=48, H1=22, H4=11; 4 unclassified M15 missing slots, 1 H1 slot,
  0 H4 missing slots. These are last observed **metadata**, not a
  real-time quote, a per-bar source attestation, or full historical
  cross-frame validation. H4 still lacks 10 strict contiguous closes
  for a 21-bar technical warmup, and 39 for a 50-bar paper-history floor.
- Review Render demo last independently verified live on `a8b5fe02`;
  private coordinator on `b01574f2`. **No redeploy in this batch.**
  Production untouched. Keep these distinct from GitHub HEAD.
- Gmail check after November 17: no new support reply found from
  BiQuote, CFI, or Twelve Data in that period. BiQuote follow-up already
  sent on November 18 requesting exact MT5 broker identity,
  broker-specific session/DST proof and confirmation that XAUUSD is
  spot/CFD rather than CME order book. Do not send duplicates without
  a new reason.
- Current recommendation status stays `WAIT`, `executable=false`.
  Source rights + session/calendar, independent historical BID/ASK
  execution assumptions, synchronized macro/GC news and true
  **untouched, externally corroborated after-cost prospective** paper
  outcomes remain mandatory. Code and offline CI cannot invent them.

