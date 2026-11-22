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
