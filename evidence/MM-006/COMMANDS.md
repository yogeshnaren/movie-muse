# MM-006 — ACL, tenancy, audit, and collaboration semantics — implementer evidence

Item: MM-006
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-006.pass_record. Only an independent
verifier may do that.

## Scope

`scope_keys: [module.identity, module.authorization, module.audit]`
- `src/movie_muse/identity/**` public `movie_muse.identity.api`
- `src/movie_muse/authorization/**` public `movie_muse.authorization.api`
- `src/movie_muse/audit/**` public `movie_muse.audit.api`
- `tests/identity/**`, `tests/authorization/**`, `tests/audit/**`

Did not edit MM-001 through MM-005 owned files, `pyproject.toml`,
persistence SQLite migrations, `movie_muse.schemas`, revisions/sync/document
source, `tests/__init__.py`, or the status ledger.

## What was built

1. **Identity.** Actors (human vs `integration_service`), organizations/tenants,
   explicit invitations (`pending`/`accepted`/`revoked`), and membership at the
   current ACL epoch. Accepting an invite writes membership and adds the actor
   to `authorized_actor_ids` workspace meta. Revoking membership increments
   `acl_epoch`, records an append-only epoch binding, removes the actor from
   `authorized_actor_ids`, and calls `SyncProtocol.quarantine_unsynced`.
   Project owner membership cannot be revoked.

2. **Authorization.** Deny-by-default `authorize(principal, action, resource, *, acl_epoch, context) -> Decision`.
   Resources: organization, project, document, branch, artifact, operation.
   Roles: owner, administrator, writer, director, producer, department
   contributor, reviewer, viewer, integration service.
   Explicit matrix (tested):
   - writer: read, comment, propose, accept. **Cannot** manage ACL, export, or merge.
   - viewer: read only. **Cannot** export.
   - producer: `view_sensitive_financial`; **not** `view_rights`.
   - administrator: `view_rights`; **not** `view_sensitive_financial`.
   - owner: both financial and rights; generic read is not sufficient for either.
   Craft confirmation: human `department_contributor` matching `resource.department`
   is allowed; AI/integration principals are denied even with a department role.
   Protected-branch merge/accept requires owner/manage-ACL **and** explicit
   `allow_protected`. Versioned `permission_snapshot_id` invalidates on
   membership/epoch change; worker re-check with a stale epoch or snapshot denies.

3. **Tenant isolation / confused deputy.** A principal in org A cannot read org B.
   Passing another tenant's project id with a valid org A token (resource
   `organization_id` spoofed to A) is `confused_deputy`.

4. **Modes.** Writer/Director/Producer/AD/Room/Department/Investor/Field are
   projections of one canonical project. `project_view` reads the live head
   revision id; it does not copy or fork document state. Custom composition is
   the union of mode actions and remains deny-by-default for unspecified
   actions. Two modes over the same workspace see the same head revision id.

5. **AuthorizedRevisionService.** Thin facade over `RevisionService` (no edits
   to the revisions module). Mutating commands (patch/merge/accept/export/craft
   confirm) re-run `authorize()` first.

6. **Audit.** Append-only records: actor, effective principal, operation,
   object, before/after revision IDs, policy decision, time, correlation ID,
   ACL epoch, chained integrity hash. `update`/`delete` raise
   `AuditImmutableError`. Replay/list is append-sequence order. Every
   `authorize()` allow and deny is recorded when an `AuditLog` is bound.

Storage is content-addressed blobs + `workspace_meta` index digests
(`identity.index_digest`, `audit.index_digest`). No new SQLite tables.
`set_meta("acl_epoch", ...)` and `set_meta("authorized_actor_ids", json list)`
use keys already owned by MM-004.

## Commands

See `quality-commands.txt`. Headline (committed tree `d4677736bdbb92ac0e3fe53ffefee167a3ea5993`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 90 source files |
| `PYTHONPATH=src python3 -m pytest tests/identity tests/authorization tests/audit -q` | 37 passed |
| `PYTHONPATH=src python3 -m pytest tests/identity tests/authorization tests/audit tests/revisions tests/persistence tests/sync -q` | 82 passed |
| `PYTHONPATH=src python3 -m pytest` | 315 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-006` only |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-006` | `a738a7f665bbdac66df6f37ece3eaab38ddc9148aae60bf322ddbc86fa4efcb4` |
| `./scripts/verify_all.sh` | fail-closed `NOT_READY` missing `migrations_backup_and_recovery` |

The named `scripts/gates/migrations_backup_and_recovery.sh` is not added
because introducing it requires changing MM-001-owned `tests/release/` (the
fail-closed test currently asserts that missing gate name). That would STALE
MM-001. Expected for this package.

Implementation commit (code + tests): `d4677736bdbb92ac0e3fe53ffefee167a3ea5993`
Input fingerprint at that commit: `a738a7f665bbdac66df6f37ece3eaab38ddc9148aae60bf322ddbc86fa4efcb4`
UTC: `2026-09-01T13:42:27Z`

## Known limitations

- Membership/ACL/audit live in module-owned blob indexes, not SQL tables.
- `AuthorizedRevisionService` is the host-facing ACL gate; raw `RevisionService`
  still exists for MM-005 internals and tests.
- Investor mode is read-only over approved-artifact field names; MM-007 owns
  the actual artifact objects.
- `verify_all.sh` remains fail-closed until later packages add the named gates.

## Required external gates

None for MM-006. Live/sandbox gates belong to later packages.

## Verifier instructions

1. Fresh detached checkout of the implementation commit
   `d4677736bdbb92ac0e3fe53ffefee167a3ea5993` (or this evidence commit; owned-path
   fingerprint must still be
   `a738a7f665bbdac66df6f37ece3eaab38ddc9148aae60bf322ddbc86fa4efcb4`).
   Do not edit the canonical ledger.
2. Confirm MM-001 through MM-005 are current PASS and MM-006 is IN_PROGRESS.
3. Recompute `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-006`.
4. Run ruff, mypy src, focused pytest (`tests/identity tests/authorization tests/audit`),
   affected (`tests/revisions tests/persistence tests/sync`), and full pytest.
5. Confirm hosts import `movie_muse.identity.api`, `movie_muse.authorization.api`,
   and `movie_muse.audit.api` only (boundary tests plus
   `python3 scripts/mm_status.py boundaries`).
6. Probes (must all hold):
   - **Deny-by-default:** unknown principal, unknown action, unknown resource,
     and `authorize()` with no bound authority all deny.
   - **Tenant / confused-deputy:** principal in org A cannot read org B;
     copying org B's project id onto an org A resource/token is `confused_deputy`.
   - **Revoke + quarantine:** invite → accept → local save queues outbox;
     revoke bumps `acl_epoch`, unsynced outbox becomes `recovery_only`,
     `flush_outbox` does not upload it, blobs remain, remaining owner can still save.
   - **Craft-decision AI deny:** human department contributor matching the
     department is allowed; integration principal is denied.
   - **Modes same canon:** writer and director (and composed modes) `project_view`
     head revision ids equal `RevisionService.canon_head_id()`; no forked project copy.
   - **Audit hash:** append-only; `update`/`delete` fail; replay recomputes
     `integrity_hash` and chain `previous_hash`.
   - **Worker re-check:** after epoch bump, authorize with the old epoch or old
     `permission_snapshot_id` denies (`stale_acl_epoch` / `stale_snapshot`).
   - **Protected branch:** writer merge with `allow_protected=True` is still
     denied; owner requires explicit `allow_protected`.
   - **Sensitive data:** writer/viewer `read` allow does not grant
     `view_sensitive_financial` or `view_rights`.
7. Airplane/outage: with connectivity/auth/subscription/sync/AI flags set,
   `authorize()` still allows the local owner (no network).
8. Do not treat this implementer record as PASS.
