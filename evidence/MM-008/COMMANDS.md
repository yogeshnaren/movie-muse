# MM-008 — Durable worker and transactional job infrastructure — implementer evidence

Item: MM-008
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-008.pass_record.

## Scope

`scope_keys: [module.jobs, runtime.worker]`
- `src/movie_muse/jobs/**` public `movie_muse.jobs.api`
- `src/movie_muse/worker/**` public `movie_muse.worker.api`
- `tests/jobs/**`, `tests/worker/**`

Did not edit MM-001 through MM-007 owned files, `pyproject.toml`,
persistence SQLite migrations, schemas, or `tests/__init__.py`.

## What was built

1. **JobService.** Durable queue in content-addressed blobs + `jobs.index_digest`.
   Enqueue, lease (priority then FIFO), heartbeat, expire, complete, fail,
   cancel, jobs-owned outbox/inbox, once-only canonical mutations keyed by
   idempotency. No new SQLite tables and no writes to MM-004 outbox/inbox tables.
2. **WorkerRuntime.** Named lease owner over JobService. Records provider
   responses separately from persist so a crash between those steps is
   recoverable. Replay pending outbox applies once.
3. **Commit guards.** Complete re-authorizes with the job's captured ACL epoch
   and permission snapshot; stale epoch/snapshot deny and do not apply.
   Input fingerprint is recomputed; mismatch is retryable and does not apply.
   Cost over budget dead-letters. Canceled leases cannot commit.
4. **Retry.** Provider `fail(retryable=True)` uses exponential backoff.
   Lease timeout (crash) requeues immediately so another worker can finish.
5. **Trace.** Events carry `trace_id` without screenplay content.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`2c815f5e8d797bb89e92a4fcaeda1bc37c224b25`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 106 source files |
| `PYTHONPATH=src python3 -m pytest tests/jobs tests/worker -q` | 19 passed |
| `PYTHONPATH=src python3 -m pytest tests/jobs tests/worker tests/authorization tests/persistence tests/audit -q` | 66 passed |
| `PYTHONPATH=src python3 -m pytest` | 358 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-008`, `MM-010` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-008` | `7ff88167512ca1259071e535e107c4c3ac8190490ac01a32e99f35798f732cc6` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `2c815f5e8d797bb89e92a4fcaeda1bc37c224b25`
Input fingerprint at that commit: `7ff88167512ca1259071e535e107c4c3ac8190490ac01a32e99f35798f732cc6`
UTC: `2026-09-01T15:36:00Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-008` at
the evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- Job payloads/results are JSON objects; model routing belongs to MM-009.
- Real provider adapters are not in this package; delivery uses a local inbox.
- `verify_all.sh` remains fail-closed until later packages add named gates.

## Required external gates

None for MM-008.

## Verifier instructions

1. Fresh detached checkout of `2c815f5e8d797bb89e92a4fcaeda1bc37c224b25` or
   this evidence commit. Recompute fingerprint MM-008 at that HEAD. At
   `2c815f5` it must be
   `7ff88167512ca1259071e535e107c4c3ac8190490ac01a32e99f35798f732cc6`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-007 are current PASS and MM-008 is IN_PROGRESS.
3. Run ruff, mypy src, focused pytest (`tests/jobs tests/worker`), affected
   (`tests/authorization tests/persistence tests/audit`), and full pytest.
4. Probes:
   - Duplicate idempotency_key returns the same job and applies once.
   - Kill/restart: lease, record provider response, crash, expire lease,
     another worker leases and persist_provider_result applies once.
   - Outbox replay after complete does not duplicate canonical mutation.
   - After membership revoke, complete denies stale_acl_epoch and applies nothing.
   - Changed input fingerprint denies commit (retryable) and applies nothing.
   - Cancel of a leased job prevents complete.
   - Retryable fail backs off then dead-letters with explainable error.
   - Cost budget exceeded dead-letters with no mutation.
   - No new SQLite tables; airplane mode works locally.
   - Public API: hosts import jobs.api / worker.api only.
5. Do not treat this implementer record as PASS.
