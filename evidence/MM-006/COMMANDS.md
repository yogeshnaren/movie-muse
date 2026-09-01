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
   `authorized_actor_ids`, and quarantines **only that principal's** unsynced
   outbox envelopes for the project (`recovery_only`). Authorized collaborators
   remain `queued_for_sync`. Project owner membership cannot be revoked.
   `invite`, `revoke_invitation`, and `revoke_membership` require an accepted
   owner or administrator membership on the target project (`AclDeniedError`
   otherwise). `accept_invitation` remains invitee-only. Identity does not
   import `authorization.policy` (cycle + public-sibling boundary); the local
   `_MANAGE_ACL_ROLES` set must match `ROLE_ACTIONS` for `Action.MANAGE_ACL`.
   Registered actor principal kind and tenant binding are immutable
   (`ActorImmutableError` on overwrite). `permission_snapshot_id` hashes actor
   identity as well as memberships and ACL epoch.

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
   After the project binding is known, `authorize()` still resolves the scoped
   resource id: documents via `LocalWorkspace.reopen`, branches via
   `RevisionService.get_branch`, artifacts and operations via an authorization
   catalog (`declare_artifact` / `declare_operation`). Unknown same-project
   child IDs are `unknown_resource`.

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
   `AuditLog.append` loads, mutates, and commits the content-addressed index
   inside `workspace.store.transaction()` (`BEGIN IMMEDIATE`) so two
   `LocalWorkspace` connections cannot last-writer-win the chain.

Storage is content-addressed blobs + `workspace_meta` index digests
(`identity.index_digest`, `audit.index_digest`). No new SQLite tables.
`set_meta("acl_epoch", ...)` and `set_meta("authorized_actor_ids", json list)`
use keys already owned by MM-004.

## Independent FAIL at `680d726` and follow-up

Verifier `movie-muse-independent-verifier/gpt-5.6-sol/2026-09-01T13:54:08Z`
FAILED `680d726fdca82a88f62bdd59403338d76592c596` (fingerprint
`a9c45bce38cbfc90f707e7be9e0aede78e747784ec86e2b29156a17ebb6d7da2`).

Required probes that PASSed then still apply. Two FAILs:

1. Writer was `role_denied` for `MANAGE_ACL` but `IdentityService.invite` /
   `revoke_membership` trusted `actor_id` and mutated ACL. Fix: deny-by-default
   `MANAGE_ACL` on every ACL-mutating identity method; regression
   `test_writer_cannot_mutate_acl_through_identity_service`.
2. Two concurrent `AuditLog.append` calls both returned sequence 1; replay
   kept one record. Fix: serialize append index updates in `BEGIN IMMEDIATE`;
   regression    `test_concurrent_appends_keep_unique_chained_sequences`.

## Independent FAIL at `c2b3850` and follow-up

Verifier `movie-muse-independent-verifier/gpt-5.6-sol/2026-09-01T14:12:37Z`
FAILED `c2b3850c6d190e35fc223f1a9b5260cb36fe3cda`. Prior ACL-mutation and
concurrent-audit FAILs re-probed PASS. Deny-by-default FAILed: unknown
document, branch, artifact, and operation IDs under a known project were
ALLOWED. Fix: resolve each resource kind before role evaluation; regression
`test_unknown_scoped_resources_on_a_known_project_are_denied`.

## Independent FAIL at `dd9b0b5` and follow-up

Verifier `movie-muse-independent-verifier/gpt-5.6-sol/2026-09-01T14:26:57Z`
FAILED `dd9b0b575e60e0a550f62698430f041f9bab6e51`. Prior ACL-mutation,
concurrent-audit, and unknown-scoped-resource FAILs re-probed PASS. Revoke
quarantine FAILed: owner and writer queued envelopes both became
`recovery_only`. Fix: `IdentityService` quarantines only envelopes whose
`actor_id` and `project_id` match the revoked membership; regression
`test_revoke_quarantines_only_the_revoked_principal_outbox`.

## Independent FAIL at `4a90ca9` and follow-up

Verifier `movie-muse-independent-verifier/gpt-5.6-sol/2026-09-01T14:36:32Z`
FAILED `4a90ca9737553a37b41b39d2fb083ea4653a3867`. Prior FAILs re-probed PASS.
`register_actor` overwrote an integration actor as human without changing
epoch or snapshot, after which `confirm_craft_decision` succeeded. Fix:
immutable principal kind/tenant binding; snapshot includes actor identity;
regressions
`test_integration_actor_cannot_be_reclassified_as_human_for_craft` and
`test_register_actor_is_idempotent_and_rejects_kind_overwrite`.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`6b2460032d81a2356130dbffb076ab24caeb2b43`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 91 source files |
| `PYTHONPATH=src python3 -m pytest tests/identity tests/authorization tests/audit -q` | 45 passed |
| `PYTHONPATH=src python3 -m pytest tests/identity tests/authorization tests/audit tests/revisions tests/persistence tests/sync -q` | 90 passed |
| `PYTHONPATH=src python3 -m pytest` | 323 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-006` only |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-006` | `886781ca4d93707bb135c97fc32ef2892f2c40bf41bba9718eed7a8ee8caf96f` |
| `./scripts/verify_all.sh` | fail-closed `NOT_READY` missing `migrations_backup_and_recovery` |

The named `scripts/gates/migrations_backup_and_recovery.sh` is not added
because introducing it requires changing MM-001-owned `tests/release/` (the
fail-closed test currently asserts that missing gate name). That would STALE
MM-001. Expected for this package.

Implementation commit (code + tests): `6b2460032d81a2356130dbffb076ab24caeb2b43`
Input fingerprint at that commit: `886781ca4d93707bb135c97fc32ef2892f2c40bf41bba9718eed7a8ee8caf96f`
UTC: `2026-09-01T14:40:26Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-006` at
the evidence commit will differ because `verification_commit` is hashed.
Owned paths excluding `evidence/**` and `docs/working-log.md` are unchanged.

## Known limitations

- Membership/ACL/audit live in module-owned blob indexes, not SQL tables.
- `AuthorizedRevisionService` is the host-facing ACL gate; raw `RevisionService`
  still exists for MM-005 internals and tests.
- Artifacts have no MM-007 store yet; `declare_artifact` is the fail-closed
  existence authority until that package binds real objects. Same for
  operations via `declare_operation`.
- `verify_all.sh` remains fail-closed until later packages add the named gates.

## Required external gates

None for MM-006. Live/sandbox gates belong to later packages.

## Verifier instructions

1. Fresh detached checkout of implementation commit
   `6b2460032d81a2356130dbffb076ab24caeb2b43` or this evidence commit.
   Recompute `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-006`
   at that HEAD. At `6b24600` it must be
   `886781ca4d93707bb135c97fc32ef2892f2c40bf41bba9718eed7a8ee8caf96f`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-005 are current PASS and MM-006 is IN_PROGRESS.
3. Run ruff, mypy src, focused pytest (`tests/identity tests/authorization tests/audit`),
   affected (`tests/revisions tests/persistence tests/sync`), and full pytest.
4. Confirm hosts import `movie_muse.identity.api`, `movie_muse.authorization.api`,
   and `movie_muse.audit.api` only (boundary tests plus
   `python3 scripts/mm_status.py boundaries`).
5. Probes (must all hold), including the prior independent FAILs:
   - **Deny-by-default:** unknown principal, unknown action, unknown project,
     unknown same-project document/branch/artifact/operation IDs, and
     `authorize()` with no bound authority all deny (`unknown_resource` for
     missing objects).
   - **Non-owner ACL management (prior FAIL):** grant a writer membership;
     confirm `AuthorizationService` denies `MANAGE_ACL`; as that writer call
     `IdentityService.invite` (administrator), `revoke_invitation`, and
     `revoke_membership`. All must raise `AclDeniedError`; ACL epoch and
     memberships must be unchanged.
   - **Tenant / confused-deputy:** principal in org A cannot read org B;
     copying org B's project id onto an org A resource/token is `confused_deputy`.
   - **Revoke + quarantine:** invite → accept → local save queues outbox;
     revoke bumps `acl_epoch`, **only the revoked actor's** unsynced outbox
     becomes `recovery_only`, other authorized principals remain
     `queued_for_sync`, `flush_outbox` does not upload the revoked work,
     blobs remain, remaining owner can still save.
   - **Craft-decision AI deny:** human department contributor matching the
     department is allowed; integration principal is denied. Re-registering
     the same actor id as `human` raises `ActorImmutableError`; epoch and
     snapshot stay unchanged; `confirm_craft_decision` remains denied.
   - **Modes same canon:** writer and director (and composed modes) `project_view`
     head revision ids equal `RevisionService.canon_head_id()`; no forked project copy.
   - **Audit hash:** append-only; `update`/`delete` fail; replay recomputes
     `integrity_hash` and chain `previous_hash`.
   - **Concurrent audit append (prior FAIL):** two `LocalWorkspace` connections,
     two-party barrier, concurrent `AuditLog.append`; both succeed with unique
     sequences `{1, 2}`; replay retains both chained records.
   - **Worker re-check:** after epoch bump, authorize with the old epoch or old
     `permission_snapshot_id` denies (`stale_acl_epoch` / `stale_snapshot`).
   - **Protected branch:** writer merge with `allow_protected=True` is still
     denied; owner requires explicit `allow_protected`.
   - **Sensitive data:** writer/viewer `read` allow does not grant
     `view_sensitive_financial` or `view_rights`.
6. Airplane/outage: with connectivity/auth/subscription/sync/AI flags set,
   `authorize()` still allows the local owner (no network).
7. Do not treat this implementer record as PASS. `verify_all.sh` must still
   fail closed on missing `migrations_backup_and_recovery`; that is not an
   MM-006 failure.
