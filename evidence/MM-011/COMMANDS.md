# MM-011 — Machine-enforceable dependency and invalidation engine — implementer evidence

Item: MM-011
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-011.pass_record.

## Scope

`scope_keys: [module.dependencies]`
- `src/movie_muse/dependencies/**` public `movie_muse.dependencies.api`
- `tests/dependencies/**`

Did not edit MM-001 through MM-010 owned files except MM-011 IN_PROGRESS
bookkeeping (`movie_muse_build_status.yaml`, `docs/working-log.md`). Did not
implement MM-012 or later. Did not mark PASS.

## What was built

1. **DependencyEngine / GraphService.** Typed nodes (source_revision,
   accepted_claim, configuration, model, rights_record, derived_projection,
   artifact_version) and edges. Content/config/model input hashes. Cycle
   prevention on `add_edge`. Storage is blobs + `dependencies.index_digest`.
   No new SQLite tables.
2. **Invalidation.** `invalidate_inputs` / `invalidate_for_change_set`
   compute the minimal frontier (direct consumers) and transitive dependent
   closure, mark that closure stale, and enqueue `recompute_node` jobs via
   `JobService` with captured `acl_epoch` and `permission_snapshot_id`.
3. **Recompute.** A node becomes current only after `recompute_node` when
   all upstreams are current; otherwise it stays stale. Stale remains
   viewable and labeled (`current=false`, `labeled_stale=true`).
4. **Export.** Stale export without override+audit raises
   `StaleExportDeniedError`. Override requires a reason and writes an audit
   record. Payload never reports stale as current.
5. **Property tests.** Incremental invalidation matches a full DAG walk;
   incremental recompute hashes match a clean full recompute.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`f28bb51f8bd7d0f6050ff6958e3f8bc48cfdb003`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: 140 source files |
| `PYTHONPATH=src python3 -m pytest tests/dependencies -q` | 25 passed |
| `PYTHONPATH=src python3 -m pytest tests/dependencies tests/jobs tests/worker tests/revisions tests/authorization -q` | 92 passed |
| `PYTHONPATH=src python3 -m pytest` | 448 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-011` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-011` | `1a8f5e4316807052860c694c7f5404bea2a6fabcbda95fac06f533dffba8d79e` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `f28bb51f8bd7d0f6050ff6958e3f8bc48cfdb003`
Input fingerprint at `f28bb51`: `1a8f5e4316807052860c694c7f5404bea2a6fabcbda95fac06f533dffba8d79e`
UTC: `2026-09-01T17:14:59Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-011` at
the evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- Invalidation after an accepted ChangeSet is an application-layer hook
  (`invalidate_for_change_set`); revisions internals were not modified.
- Recompute is a local deterministic hash refresh, not a model/provider
  regeneration. Later extraction packages will attach real derived work.
- `verify_all.sh` remains fail-closed until later packages add named gates.

## Required external gates

None new for MM-011.

## Verifier instructions

1. Fresh detached checkout of `f28bb51f8bd7d0f6050ff6958e3f8bc48cfdb003` or
   this evidence commit. Recompute fingerprint MM-011 at that HEAD. At
   `f28bb51` it must be
   `1a8f5e4316807052860c694c7f5404bea2a6fabcbda95fac06f533dffba8d79e`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-010 are current PASS and MM-011 is IN_PROGRESS
   with `pass_record: null`.
3. Run ruff, mypy src, focused pytest (`tests/dependencies`), affected
   (`tests/jobs tests/worker tests/revisions tests/authorization`), and full
   pytest.
4. Probes:
   - Cycle: `add_edge` that would cycle raises `CycleError`.
   - Frontier vs closure: a leaf change stales dependents, not siblings.
   - Diamond: both branches and join become stale.
   - Property: incremental invalidation equals `stale_closure_from_scratch`.
   - Stale export denied; override+audit allowed; payload `current` is false.
   - Recompute job appears in `JobService` with type `recompute_node`.
   - Crash/reopen reloads graph from blobs; no new SQLite tables;
     `dependencies.index_digest`.
   - Concurrent `add_edge` both persist.
   - Viewer cannot `add_node`; can `view_node`.
   - `invalidate_for_change_set` after `RevisionService.apply_change_set`
     stales nodes whose inputs include the new revision.
5. Do not treat this implementer record as PASS.
