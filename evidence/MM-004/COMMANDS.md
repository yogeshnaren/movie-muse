# MM-004 — Local-first persistence, migrations, and sync primitives — implementer evidence

Item: MM-004
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-004.pass_record. Only an independent
verifier may do that.

## Scope

`scope_keys: [module.persistence, module.sync]`
- `src/movie_muse/persistence/**` public `movie_muse.persistence.api`
- `src/movie_muse/sync/**` public `movie_muse.sync.api`
- `tests/persistence/**`, `tests/sync/**`

## What was built

1. Embedded SQLite store (WAL, `synchronous=FULL`) plus content-addressed blob
   files (`tmp` + fsync + rename).
2. Crash-safe save: blob is durable, then one transaction writes the immutable
   revision and the outbox envelope. `SaveAck` is returned only after commit.
   Rolled-back transactions are not acknowledged.
3. Airplane-mode / auth / subscription / sync / AI outages cannot lock
   open/edit/save/reopen/export of already-local work. Upload flush is refused.
4. Forward migrations (v1 initial schema, v2 additive `last_export_at`) that are
   idempotent and retry the unfinished version after a crash.
5. Backup (sqlite backup API + blob copy) and corruption recovery from backup.
6. Idempotent sync envelopes (project, branch, base/resulting revision, hash,
   actor, device, operation ID, schema version, ACL epoch). Duplicates ignored;
   unknown bases buffered then applied; non-head ancestry is an explicit
   conflict (no last-writer-wins). Revoked unsynced work is quarantined
   recovery-only, never uploaded or destroyed.
7. Unambiguous workspace status: saved locally, queued for sync, synced,
   backed up, conflicted, recovery-only.

Canonical persistence is typed `ScreenplayDocument`. Editor JSON is never stored.

## Commands

See `quality-commands.txt`. Headline:

| Command | Result |
|---|---|
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 61 source files |
| `python3 -m pytest tests/persistence tests/sync -q` | 18 passed |
| `python3 -m pytest` | 248 passed, 1 warning |
| `python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `python3 scripts/mm_status.py boundaries` | 0 violations |
| `python3 scripts/mm_status.py secrets` | 0 hits |
| `./scripts/verify_all.sh` | fail-closed `NOT_READY` missing `migrations_backup_and_recovery` |

The named `scripts/gates/migrations_backup_and_recovery.sh` is not added yet
because introducing it requires changing MM-001-owned `tests/release/` (the
fail-closed test currently asserts that missing gate name). That would STALE
MM-001/MM-002. Python tests already cover migrations, backup, and recovery.
The shell gate should land together with a status-invariant fail-closed test
after independent verification of this package.

## Verifier instructions

1. Fresh detached checkout of this commit. Do not edit the canonical ledger.
2. Confirm MM-001 and MM-002 are current PASS.
3. Recompute `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-004`.
4. Run ruff, mypy, `pytest tests/persistence tests/sync`, and full pytest.
5. Probe: airplane-mode save/reopen/export; auth outage does not lock local
   save; uncommitted transaction is not an ack; corrupt sqlite restores from
   backup; v1 database migrates to current; duplicate envelopes; out-of-order
   envelopes apply after the missing base arrives; conflicting heads are
   conflicted, not last-writer-wins.
6. Confirm other modules import `movie_muse.persistence.api` and
   `movie_muse.sync.api` only.
