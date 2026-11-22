# Synthetic paper journal — existing-volume activation (review only)

**Current state (2026-11-22): BLOCKED.** The review Render service
`gold-precision-v3-review-demo` is **Free**, has no verified persistent
disk, and therefore must not initialize a paper journal on its ephemeral
filesystem. Do **not** change the production service, create a paid disk,
set these variables, or enable automatic recording before the operator
separately authorizes a persistent-volume plan and data access.

## What is already prepared (offline only)

- `paper_volume_bootstrap.js --check` verifies an **existing** mounted disk
  and an unused set of file names. It never writes.
- `paper_volume_bootstrap.js --initialize` is an explicit one-time
  **operator-only** command. It fails closed if the disk is unverified,
  required paths are missing, or any target file already exists. It
  creates only an **empty synthetic** SQLite journal and a local
  checkpoint/manifest, then validates their freeze and hash ancestry.
- The existing paper startup recovery gate verifies the journal and
  checkpoint on boot. The existing private paper reports endpoint
  remains WAIT unless this gate and volume preflight both pass.
- The synthetic event recorder is a dormant, manually called integration
  module. Neither initialization nor the server starts a worker or places
  any trading orders. No live data vendor is connected.
- A checkpoint on the SAME disk does **not** protect against complete
  disk deletion. Offsite backup design and user authorization are separate.

## Operator steps ONLY after storage approval and provisioning

1. Attach a Render-supported persistent disk to an approved **review**
   service. Do not touch production or the current Free plan without
   explicit approval. Confirm mountpoint and that data survives a
   service restart.
2. Use a private service shell or approved administrator deployment tool
   to set `GOLD_SYNTHETIC_PAPER_DISK_MOUNT` to the exact existing mount
   root, for example `/var/data`. No browser input controls these paths.
3. Run `node coordinator/paper_volume_bootstrap.js --check` and confirm
   `EXTERNAL_VOLUME_VERIFIED_INITIALIZATION_DISABLED`. Any other
   result blocks initialization.
4. After independent authorization of disk and the operator action,
   invoke `node coordinator/paper_volume_bootstrap.js --initialize`
   **once**. It must report
   `EMPTY_SYNTHETIC_STORAGE_PREPARED_NOT_RECORDING`.
5. Configure these read-only monitoring paths (example ONLY):
   - `GOLD_SYNTHETIC_PAPER_JOURNAL=/var/data/synthetic-paper.sqlite3`
   - `GOLD_SYNTHETIC_PAPER_DISK_MOUNT=/var/data`
   - `GOLD_SYNTHETIC_PAPER_CHECKPOINT=/var/data/synthetic-checkpoint.sqlite3`
   - `GOLD_SYNTHETIC_PAPER_CHECKPOINT_MANIFEST=/var/data/synthetic-checkpoint.json`
6. Restart the **review** service. Confirm startup reports pass with
   `WAIT`, no orders, and **zero** closed trades. Verify that a second
   initialization attempt is rejected and does not alter stored bytes.
7. Before any ongoing synthetic paper logging, separately approve and
   configure an operator-controlled event source, a persistent backup
   destination outside the same volume, and actual data rights. None of
   these are enabled by this bootstrap.

**Never:** create sample profits on production, use BiQuote research
quotes as licensed broker fills, trust a free Render filesystem as
durable, automatically restore over an existing SQLite file, or
convert experimental BUY/SELL into real transactions.
