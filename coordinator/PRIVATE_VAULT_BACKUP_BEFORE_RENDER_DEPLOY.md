# Gold Precision — preserve the live private vault BEFORE a Render deploy

**Status as of 2026-11-22: HOLD. Do not restart or redeploy either
service on the assumption that logs or GitHub CI have backed up the data.**

The Render review web service and the private monitoring coordinator are
separate. The review service was last observed on the Free plan, and no
persistent disk was attested. The private coordinator does not expose
a file-copy or shell operation through the connected Render app. The
verified Render *application logs* establish only time-stamped, sanitized
monitoring activity; they do **not** contain a recoverable copy of the
signed archive of XAUUSD quotes or closed candles.

## Verified hosting facts (Render account inspected 2026-11-22)

- The private service `gold-precision-coordinator` has a **2 GB persistent
  disk mounted at `/var/data`**; this does not prove the sealed vault file
  exists on that disk, or that an offsite backup exists. The configured
  vault directory comes from `GPP_BIQUOTE_FORWARD_VAULT_DIR`, **not**
  necessarily from the `DATA_DIR` default.
- The review web service `gold-precision-v3-review-demo` is **Free** and
  has **no attached persistent disk**. Neither service is auto-deployed
  from review-branch commits (`autoDeploy: no`).
- The coordinator's last observed live deploy was `b01574f` on Nov 18.
  That **running image** does not include the newly developed copy/restore
  tools. The **review-branch Dockerfile** now stages these modules for a
  future approved build, but no new image has been deployed. **Do not
  redeploy just to install them**; code in GitHub is not equivalent to a
  command already available on the service.
- Render supports an interactive **Shell** on the running private service
  under its Dashboard. The connected Render API tools cannot execute a
  shell or read private files. A signed-in owner can open the service's
  Shell page without changing the deployed build. Render documentation:
  https://render.com/docs/ssh

### Safe read-only owner inventory (no prices, paths, tokens or file contents)

Inside the **existing running coordinator** via Dashboard → Shell, an
owner may paste this check. It only says whether the configured vault is
on the persistent disk, exists, and has owner-only permissions. It DOES
NOT export, copy, restart, or verify restore. It does not echo the private
vault directory or environment values:

```sh
python3 - <<'PY'
import os, pathlib, stat
v=os.environ.get("GPP_BIQUOTE_FORWARD_VAULT_DIR","")
configured=v.startswith("/var/data/") and ".." not in pathlib.Path(v).parts
file=pathlib.Path(v)/"biquote-forward-private-v1.json" if configured else None
exists=False; owner_only=False
if file is not None:
    try:
        s=file.lstat()
        exists=stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode)
        owner_only=exists and s.st_uid==os.getuid() and s.st_mode & 0o077==0
    except OSError:
        pass
print("persistentVaultPathConfigured=",configured)
print("privateVaultFilePresent=",exists)
print("vaultFileOwnerOnly=",owner_only)
print("offsiteBackupVerified=",False)
print("reviewDeployApproved=",False)
PY
```

### Check signed vault integrity on the ALREADY running coordinator (no deploy)

This short optional command works with the `biquote_private_forward_vault.py`
module already included in the Nov 18 running image. It reads the **real**
private vault, if configured, and prints ONLY sanitized counts. It does not
request data, copy, upload, overwrite, restart, subscribe, or trade:

```sh
cd /app && python3 - <<'PY'
import json, os, pathlib
from biquote_private_forward_vault import FILE, FRAMES_ORDER, load_vault
p = os.environ.get("GPP_BIQUOTE_FORWARD_VAULT_DIR", "")
result = {"status":"BLOCKED", "sealedVaultValidated":False,
          "closedCounts":None,"quoteObservations":None,
          "offsiteBackupVerified":False,"reviewDeployApproved":False,
          "signal":"WAIT","executable":False}
try:
    directory=pathlib.Path(p)
    if (p.startswith("/var/data/") and ".." not in directory.parts
            and (directory / FILE).is_file()):
        vault=load_vault(directory)
        counts={tf:len(vault["closed"][tf]) for tf in FRAMES_ORDER}
        quotes=len(vault["quoteObservations"])
        if quotes and any(counts.values()):
            result.update(status="SEALED_SOURCE_LOCAL_VALID_ONLY",
                          sealedVaultValidated=True,
                          closedCounts=counts,quoteObservations=quotes)
except (OSError,ValueError,KeyError,TypeError):
    pass
print(json.dumps(result,sort_keys=True))
PY
```

**This local integrity test is not an offsite backup, and the running
container does not have the new standalone owner-inventory command.** A
future image contains `/app/biquote_owner_vault_inventory.py` with more
strict file and path checks; no future-image build/deploy is authorized by
this document. Synthetic CI tests must pass before relying on that code.

**Do not** share raw file contents, exported archives, env values, or
credentials in support chats or GitHub. A successful inventory is only the
first step. Owner-authorized, permitted private export and independent
recovery are still required. The current copy script now requires a
successful destination-directory `fsync` before it can report a verified
local copy, including on separate devices.

## Render's built-in disk snapshots: useful recovery layer, not the private vault copy

Render documents that **persistent disks** are snapshotted automatically
roughly every 24 hours, kept for **seven days**, and encrypted at rest.
This is a point-in-time **whole-disk** recovery mechanism; it is not a
verified, independently restorable, owner-controlled archive export.
Render cannot restore just the BiQuote vault from a disk snapshot, and
restoring the whole snapshot destroys any newer disk changes. **Do NOT
press Restore** on the running coordinator merely to inspect a backup.
Official documentation: https://render.com/docs/disks#disk-snapshots

The connected Render tools confirm the coordinator has a 2 GB persistent
disk mounted at `/var/data`, but do NOT list that disk's actual snapshots.
Their existence, ages, and inclusion of the sealed market archive are
therefore **not yet confirmed**. The listing endpoint is documented at
https://api-docs.render.com/reference/list-snapshots but is not exposed by
the current connected Render tooling. Never embed API tokens or short-lived
snapshot keys into source code, chat, or logs.

### Phone-friendly read-only owner check

1. Open the existing private coordinator:
   https://dashboard.render.com/pserv/srv-dbosre95efls73ete99g
2. Tap **Disk** and locate **Snapshots** (or the snapshot restore section).
   Inspect the timestamps/availability only; **do not select Restore**.
3. Open **Shell**, if available to your account, and run the already
   documented read-only sealed-vault integrity check above. Do NOT print
   provider quotes, the vault file, environment variables, or keys.
4. Only after confirming both (a) the vault file is on the persistent disk
   and (b) an actual recent snapshot exists, label this as a **possible
   seven-day disk recovery point**, not a verified offsite vault backup.

For automation-safe **offline research** on *redacted* snapshot metadata,
`biquote_render_snapshot_metadata_gate.py` accepts a JSON array of
`createdAt` UTC timestamps (in the format returned by Render) via stdin.
It never calls Render or restores a disk; it ignores and never outputs
`snapshotKey` values. Even `RECENT_SNAPSHOT_LISTED_NOT_ARCHIVE_PROOF`
means only that a caller-supplied timestamp is within 36 hours. It does
**not** verify a real Render snapshot, the inclusion of the vault, data
rights, or external recovery. Its output permanently keeps
`reviewDeployApproved:false` and `signal:WAIT`.

## Existing read-only verification tools

- `biquote_private_forward_vault.py`: the private signed owner-only
  vault `biquote-forward-private-v1.json`; validates closed M15/H1/H4
  shapes and quote chronology. **Never commit this archive to GitHub.**
- `biquote_collector_backup_preflight.py`: compares existing sealed
  source and backup files byte-for-byte, including private-file
  permissions, and detects a copy on the same physical storage device.
- `biquote_collector_restore_rehearsal.py`: restores an existing
  sealed backup to a disposable private directory, validates it, then
  destroys that test copy.
- `biquote_private_archive_predeploy_guard.py`: requires both checks,
  rejects missing or altered copies, rejects same-device copies as
  independent backups, and never promotes the result to permission
  to deploy or generate orders.

## New one-time owner-only private copy utility (not yet run on Render)

`biquote_owner_private_copy_once.py` prepares an **opt-in**, no-network
local file copy of the existing sealed vault. It does not mount disks,
encrypt, upload, subscribe, restart services or authorize trading.

- The operator first verifies that the private source and private
  destination already exist, are both owner-only (0700), and that the
  destination has no previous vault file.
- Read-only preflight (no copy):
  `python coordinator/biquote_owner_private_copy_once.py SOURCE_PRIVATE_DIR DEST_PRIVATE_DIR`
- Only AFTER independently confirming source storage/export rights,
  an approved private storage destination and authorization:
  `python coordinator/biquote_owner_private_copy_once.py SOURCE_PRIVATE_DIR DEST_PRIVATE_DIR --copy --operator-approved-private-copy`
- The copy is 0600, atomic, never overwrites, compares the source and
  destination byte-for-byte, and runs an isolated restore test. The
  source remains unchanged. The tool returns counts/booleans only,
  never raw prices, tokens, or actual directories.
- **Same-device copy is NOT backup continuity across Render deletion**.
  A different device is still not proof of an offsite recoverable copy.
  Both cases explicitly retain `reviewDeployApproved:false` and
  `externallyDurableBackupVerified:false`.

**No command has been run against the current coordinator.** The connected
Render tools do not expose owner-only filesystem access; do not use
Render application logs or GitHub fixtures as substitutes.

## Required owner-authorized export and recovery evidence

1. Through an approved private Render filesystem access method, locate
   the **current coordinator's real owner-only source vault** and its
   currently configured archive directory. Do not assume a local GitHub
   fixture is the live source; do not display raw prices or tokens in logs.
2. Obtain an explicit, operator-authorized encrypted/exported copy
   to a privately controlled persistent destination **outside the live
   source device**. Confirm its retention policy. Render logs and a
   second file inside an ephemeral container are not equivalent.
3. Verify original and backup signed envelopes, SHA-256 equality,
   frame/quote counts, first-observation timestamps and a successful
   isolated restore. Record only count/verification metadata publicly.
4. Confirm the source vault remains available after the copy and
   establish how the private coordinator will resume capture without
   overwriting its source. A restore test is not source licensing.
5. Only after independently confirming the actual archive recovery
   should an operator decide whether any Render review redeploy is
   non-destructive. Never change production or live trading.

## Current release decision

**NO DEPLOY APPROVAL.** A copied operational log report is merely
diagnostic evidence, not a market archive backup. There is no verified
offsite archive, no independent broker price rights, no forecast accuracy
proof, and no authorization to send real or paper orders. Keep the
existing review service Live on its current commit until the missing
private archive access and recovery evidence have been established.
