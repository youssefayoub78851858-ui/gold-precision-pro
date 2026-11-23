# Capital.com Demo — private price-GET isolation (review only)

The selected candidate is **Capital.com Demo**. The official Capital.com
API documentation states that API keys are **trading-capable**, not genuinely
read-only. Therefore a key must NEVER be put into the general dashboard,
signal engine, browser, public Render service, or a repository file.

## Status

- Code and deterministic mock tests prepared only on
  `review/v2-portable-tests-20261109`.
- `coordinator/capital_demo_private_get_boundary.py` permits ONLY the
  HTTPS Demo `GET /api/v1/prices/{epic}` request shape, with bounded
  fixed query parameters and exact closed-bar window validation.
- It **cannot** log in or create a session, issue POST/PUT/DELETE/order
  calls, or call the live broker host. No live transport is configured.
- Default settings reject ALL provider calls. The private collector must
  later supply an independently reviewed transport and a private archival
  callback. HTTP redirects must be forbidden at the egress layer. A
  network egress allowlist to the Demo host **and only** price route is
  required; Python method restrictions alone do not securely limit the
  privileges of a trading-capable token.
- Activation requires separate, specific approval, verified contractual
  permission for cloud/private research, an eligible and KYC-verified
  Demo account, 2FA/API setup, the broker's genuine Gold epic, and a
  session token obtained outside this module. No keys should be pasted
  into ChatGPT or committed to GitHub. Tokens must be stored in an
  approved isolated secret manager, not the mobile viewer.
- No response counts, receipt times, or synthetic tests can prove
  broker session/DST or execution price basis; independent H1/H4/M15
  parity, DXY/GC rights, costs and prospective net holdout remain open.
- NEVER set the activation environment variables just to pass tests;
  tests use disposable patched values without any remote calls.

## Double-layer redirect protection (2026-11-23)

The private HTTPS price transport now checks not only that its requested
method/URL is the exact approved Demo prices GET but also that the
**completed response URL is byte-for-byte identical to the requested URL**.
The default transport uses a redirect-rejecting HTTPS opener and no
environment proxy. The independent response check also refuses
a synthetically injected opener that follows a redirect to a trading
route and then returns HTTP 200. An opener response without a verifiable
final URL is rejected. Offline tests cover both cases; they never use
real credentials or contact a provider.

**This is application-level defense, not external network isolation.**
Before a real trading-capable Capital session token is ever provisioned,
an operator must create and verify a separate private token-holding process
with network egress controlled outside the application. IP/host firewalls
alone cannot enforce HTTP paths; a dedicated egress proxy or equivalent
layer must enforce GET plus the narrowly allowed prices route and deny
all session/order/position endpoints, redirects and unknown hosts.
The dashboard, research worker and public services must have no access
to tokens or unrestricted proxy bypass. The running Render coordinator
was NOT modified or deployed, and no such real egress isolation has
been independently attested here.

## Proposed outbound gateway contract — offline only

Added `capital_demo_egress_contract.py` and
`test_capital_demo_egress_contract.py`. The offline Python tests compare
a proposed **deny-by-default** gateway configuration to a fixed contract
and reject simulated requests to the live Capital.com trading host,
positions/orders/session routes, mutations (POST/PUT/PATCH/DELETE/CONNECT),
HTTP downgrades, redirects, extra token/query fields, and ambiguous
paths. Only the expected Demo `GET /api/v1/prices/{epic}` request
shape for M15/H1/H4 passes the *simulation*. It reuses the real
transport's strict request validator and never accesses a credential,
a socket, a vendor, a disk, or an account.

A proposed gateway must deny arbitrary proxies, CONNECT tunnels,
WebSocket upgrades, redirects and direct outbound bypasses; validate
the broker TLS certificate; enforce the method and price route **after
TLS is terminated at the trusted gateway**; and isolate trading-capable
tokens in an independent private process, inaccessible to the public UI
and research worker. The contract is a *specification*, not a deployed
proxy. Simply passing a configuration dictionary as input can never
prove that a real Render network enforces it.

Consequently the simulation always returns
`actualProxyInstalledAndEnforcing:false`,
`realNetworkIsolationVerified:false`, no provider requests, no
orders and `WAIT`, even when all synthetic requests match.
**Do not use the simulated success result to activate an API key.**
Only externally verifiable deployment details, network/bypass negative
testing on the approved isolated service, provider data rights and
an independent recovery plan can close the real connection blocker.

## What a verified account does NOT authorize

A verified Capital.com account may unlock the API integrations screen,
but does **not** grant a read-only key or any new rights for cloud-hosted
data ingestion, market-data retention or downstream analysis. Provider
support's acknowledgement/escalation is not approval from the relevant
compliance/licensing team. The selected Demo prices API supports data
retrieval in principle; its full trading-capable session tokens must
never reach any public dashboard, GitHub, or general research worker.

The offline planner now reports
`WRITTEN_PRIVATE_CLOUD_STORAGE_AND_RESEARCH_RIGHTS` as the next external
gate and `NO_TRADING_CAPABLE_API_KEY_UNTIL_RIGHTS_AND_EGRESS_ISOLATION_APPROVED`
as the operator guard. It does not assert any account holder's KYC status
and retains disabled price requests and `WAIT`.

A compliance reply must specify private Render/Linux use, data retention,
nonredistributed personal research, historical backtesting, and prospective
simulated paper use. If denied, select another properly authorized source;
do not bypass the vendor by retrying the same credentials.

## Offline private archive rehearsal — validated with synthetic data

The review branch now contains `capital_demo_private_page_store.py` and
`test_capital_demo_private_page_store.py`. The CI test uses **fictional**
`TEST.GOLD.EPIC` prices only and exercises the existing mock Demo HTTPS
GET boundary all the way to a real file on the temporary GitHub runner.
The future live coordinator and its existing sealed BiQuote vault are not
touched or deployed.

- Explicit `explicit_synthetic_rehearsal=True` is required; normal calls
  are disabled. Real Capital instrument epics are explicitly rejected.
- A pre-existing owner-owned, owner-only (0700) directory is required.
  Prices are normalized and bounded as three closed UTC-frame types.
  Each synthetic page is sealed with a local SHA-256 integrity checksum,
  written as a 0600 file via fsync and no-overwrite atomic publication.
- A repeated identical page is idempotent and **retains the first local
  rehearsal receipt time**; conflicting data, crossed BID/ASK, stale/open
  candle geometry, symlinks, unsafe permissions, hash tampering, and unknown
  response fields are rejected.
- Restart inspection re-checks both the checksum and full candle shape,
  and returns only sanitized counts, no market prices or credentials.
- Local checksum and file fsync do NOT prove provider origin, remote backup,
  approved market-data usage, genuine point-in-time first-seen quotes,
  broker sessions, or future profitability.
- No real data archive can be created by this rehearsal writer. Following
  written permission, a separately reviewed, isolated *production*
  collector and durable rights-compliant archive would have to be built
  using this tested pattern. Full-trading API credentials need an external
  network isolation policy before any provider request.

The offline test is run by
`.github/workflows/capital-demo-preconnection-offline.yml` and
does **not** connect to Capital.com or request an API key.

## Synthetic sealed three-frame replay (2026-11-23)

The separate `capital_demo_synthetic_archive_mtf_replay.py` exercise
has now passed five offline GitHub Actions regression tests with
`test_capital_demo_synthetic_archive_mtf_replay.py`.

For the fictional `TEST.GOLD.EPIC` instrument only, the test:
- Commits **16 M15, 4 H1 and 1 H4** fully closed synthetic BID/ASK
  candles to three owner-only locally sealed files.
- Reopens the already saved files, independently revalidates
  the original synthetic receipt and every price shape, reconstructs
  all three frame pages, and calls the existing BID/ASK cross-frame
  parity and missing-slot auditor.
- Rejects a missing M15 constituent, conflicting H1 aggregate,
  checksum or file-permission tampering, a missing page,
  a changed request plan, and any non-fictional instrument.
- Returns only sanitized counts and flags; no quoted prices,
  credentials, file paths or private data in the report.
- Retains `signal:WAIT`, `paperOrdersAllowed:false`,
  `executable:false`, zero provider calls and zero orders,
  even when all three synthetic frames agree.

The synthetic 4-hour sample has **only one H4 candle**, so it cannot
warm up indicators or support real signals. This workflow tests the
safe offline file-to-audit handoff, not the live private coordinator,
provider licensing, real historical continuity, a recoverable offsite
backup or price feed.

Once (and only once) a written Capital.com decision permits private
cloud collection/storage/research, the live collector will still need
separately reviewed credential isolation, the proper broker instrument,
actual bid/ask source tests, closed-candle plus market-session checks,
reliable private preservation, and independent after-cost forward paper
validation. Do not deploy/restart the existing coordinator just to
run this rehearsal.

## Offline page-arrival / decision-time guard — 2026-11-23

`capital_demo_synthetic_arrival_cutoff.py` is a non-network, non-executable
cutover rehearsal which consumes the existing sealed **fictional** multi-frame
BID/ASK pages. It reconstructs the disabled plan, verifies local M15/H1/H4
geometry, then checks that each historical page's retained **local test
receipt** is not after the explicit strategy decision time. A page received
after the decision is rejected even if every OHLC bar in it had already closed.
A decision timestamp different from the original inert plan is rejected too.

Six offline tests protect: page receipt at/before cutoff; pages retrieved
after cutoff; backdated decisions; missing M15 constituent; sealed-file
tampering/missing archive; and inability to turn the test into a market
connection by setting arbitrary environment flags. The CI test suite is
`test_capital_demo_synthetic_arrival_cutoff.py`.

**Critical limitation:** the page-level local test receipt only proves when
the synthetic historical page was saved locally *in the mock*. It is not an
authenticated timestamp from Capital.com, does not prove first observation
of individual historical bars, cannot establish a real prospective
holdout or successful trades, and must never be substituted for an
independent real first-seen audit. A local pass retains all market-data
rights, archival backup, paper and live trading gates as **false**.

This is the last class of offline timing issues to rule out before the
external compliance/egress/credentials cutover, not authorization to
collect data or redeploy the private coordinator.

## Sealed archive to real XAU/USD intake gate — offline end-to-end

`capital_demo_sealed_research_handoff.py` and its independent tests
connect the sealed fictional BID/ASK M15/H1/H4 files to the **existing**
`xauusd_feed_gate.intake_payload` and
`xauusd_research_pipeline.run_research_pipeline`. This closes a
previously untested *software integration* boundary, without changing
the frozen V3/r2 engines, public UI or private Render coordinator.

The handoff rereads the actual sealed synthetic files, verifies both
sides' multi-timeframe parity and the page-level decision cutoff,
normalizes **BID** separately from ASK, and passes an explicit
`mode:synthetic` packet through the existing source gate. It uses
the immutable original synthetic receipt timestamps, **never**
forges a receipt matching the decision time. With simulation disabled
at the research entry point, the V3/r2/diagnostics/paper engines must
report **SKIPPED**. The exact same BID bars, if relabelled as
`mode:recorded`, must be rejected by a default, unentitled
`SourcePolicy`; source-rights flags from the archive or environment
cannot authorize the handoff.

The seven added CI checks cover a valid sealed local mock; a stale
original receipt; an absent M15 constituent; a mismatching H1 aggregate;
an arrival after the decision; tampered or missing archived bytes;
and operator/environment flags that pretend permissions exist.
Only sanitized counts and hard `WAIT` status leave this routine;
no prices, file paths, tokens, network requests or trade orders.
A local pass is **not** evidence of licensed Capital.com data,
real broker feed, independent source rights, genuine market sessions,
external token isolation, offsite recovery, forward performance or
profitable paper trading.

The 16 M15 / 4 H1 / 1 H4 sample is also too small to warm indicators.
Do not deploy the running services or activate a trading-capable API
token because this offline handoff passes. A future independently
approved private live collector must still prove actual external
prerequisites before any research signals can be promoted.

## Operational handoff in order

1. Confirm **in writing** broker eligibility for Lebanon, private Render
   research rights, Demo Gold BID/ASK historical/stream basis and timing.
2. Account verification and 2FA are **separate prerequisites** for API-key
   issuance. The repository never stores or infers whether a particular
   owner has completed them. If already completed, do not repeat KYC;
   instead check the compliance decision below. Use Capital.com's own
   secure account portal only, not chat.
3. Operator establishes a dedicated network-restricted private
   **Demo-only** session/token service; review logs must redact secrets.
4. Connect only price GETs through an isolated gateway, validate each
   timestamp/price and local first-seen receipt using existing auditors.
5. Admit NO BUY/SELL or auto-paper until independent GC/DXY/news
   coverage, cost model, and untouched after-cost holdout are verified.

Current decision: WAIT. No fees, account or execution authorized.
