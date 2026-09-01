# MM-005 — Immutable revisions, branches, checkpoints, ChangeSets, and merges — implementer evidence

Item: MM-005
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-005.pass_record. Only an independent
verifier may do that.

## Scope

`scope_keys: [module.revisions]`
- `src/movie_muse/revisions/**` public `movie_muse.revisions.api`
- `tests/revisions/**`

Did not edit MM-001/MM-002/MM-003/MM-004 owned files, `pyproject.toml`,
persistence SQLite migrations, `movie_muse.schemas`, or the status ledger.

## What was built

1. Immutable content-addressed document revisions via `LocalWorkspace.save`.
   Later saves never UPDATE a prior revision row or blob. History is the
   parent chain.
2. Named branches (movable refs) with protected/archived flags. Protected
   movement requires `allow_protected=True` or fails closed. Canon is the
   head of the selected canonical branch.
3. Checkpoints: immutable named refs. Creating the same name again raises
   `CheckpointExistsError` and does not move the original.
4. ChangeSet apply only when `base_revision_id` equals the current branch
   head; otherwise `StaleBaseError`.
5. Structural three-way merge using `structural_diff(base, source)` and
   `structural_diff(base, target)`. Non-overlapping block/scene/document
   targets compose and save a merge revision. Overlap or apply failure
   persists a Merge conflict record, does not move the head, and raises
   `MergeConflictError`. Resolutions are new merge/resolution objects.
6. Immutable Proposal blobs. Accept requires PENDING and base == head.
   Rebase produces a new Proposal/ChangeSet (new ids) and marks the old
   proposal SUPERSEDED without rewriting its ChangeSet operations. Failed
   rebase marks STALE and fails closed. Rejected proposals remain loadable.
7. Restore-via-new-revision: new revision whose document equals the snapshot,
   parent = current head. Abandoned head remains in the parent chain.
8. Every accepted canonical command appends an immutable `ProjectEvent` of
   type `ScreenplayPatchAccepted` with a `payload.kind` discriminator and
   `compute_integrity_hash`. Events are append-only blobs. Replay of
   events+blobs reconstructs the stored branch head.
9. Deterministic history/diff projection plus UTF-8 text and HTML renders.
   Fixture renders are exact; live history render is stable across calls.

Persistence for branches/checkpoints/events/proposals/merges is a
revisions-owned `workspace_meta` index plus content-addressed blobs
(`put_blob` / `set_meta` / `get_meta`). No new SQLite tables.

## Commands

See `quality-commands.txt`. Headline:

| Command | Result |
|---|---|
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 70 source files |
| `PYTHONPATH=src python3 -m pytest tests/revisions tests/document tests/persistence tests/sync -q` | 65 passed |
| `PYTHONPATH=src python3 -m pytest` | 277 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-005` | `6687f03743146eb3a35ff5a81eea8df4681b8deabb469bde2bcc5712e7f55544` |
| `./scripts/verify_all.sh` | fail-closed `NOT_READY` missing `migrations_backup_and_recovery` |

The named `scripts/gates/migrations_backup_and_recovery.sh` is not added
because introducing it requires changing MM-001-owned `tests/release/` (the
fail-closed test currently asserts that missing gate name). That would STALE
MM-001. Expected for this package.

Implementation commit (code + tests): `ae8e647f86a660a82b6ac3a6a9ccbff0a0cbb058`
Input fingerprint at that commit: `6687f03743146eb3a35ff5a81eea8df4681b8deabb469bde2bcc5712e7f55544`
UTC: `2026-09-01T13:01:53Z`

## Verifier instructions

1. Fresh detached checkout of the implementation commit (or this evidence
   commit; owned-path fingerprint must still be
   `6687f03743146eb3a35ff5a81eea8df4681b8deabb469bde2bcc5712e7f55544`).
   Do not edit the canonical ledger.
2. Confirm MM-001, MM-002, MM-003, MM-004 are current PASS.
3. Recompute `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-005`.
4. Run ruff, mypy, focused pytest (`tests/revisions tests/document tests/persistence tests/sync`),
   and full pytest.
5. Confirm hosts import `movie_muse.revisions.api` only
   (`tests/revisions/test_revisions_boundaries.py` plus
   `python3 scripts/mm_status.py boundaries`).
6. Probes (must all hold):
   - **Immutable checkpoint:** create checkpoint, save again, move a branch;
     checkpoint still points at the original revision; recreating the same
     name fails closed.
   - **Stale proposal:** store a proposal, advance head with a non-overlapping
     patch, accept fails closed; rebase produces a new proposal; accept the
     rebased proposal; rejected proposals remain loadable; original ChangeSet
     operations bytes/values are unchanged.
   - **Overlapping merge fail-closed:** two branches update the same block;
     merge raises, head unchanged, merge record has conflicts (no last-writer-wins).
   - **Event replay:** append-only event blobs; recomputed `integrity_hash`
     matches; `replay_head()` equals stored branch head.
   - **Restore-via-new-revision:** restore a checkpoint; new revision id;
     document equals snapshot; abandoned head remains in parent chain.
7. Airplane/outage: with connectivity/auth/subscription/sync/AI flags set,
   branch/checkpoint/diff/export still succeed locally.
8. Do not treat this implementer record as PASS.
