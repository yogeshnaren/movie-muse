# MM-010 — Rights registry, provenance, sources, and Evidence Bundles — implementer evidence

Item: MM-010  
Role: implementer. This record is not a PASS record and does not populate
`items.MM-010.pass_record`. An independent verifier must reproduce the work.

## Dependency and scope confirmation

- MM-002, MM-004, MM-006, and MM-007 were current PASS before work.
- MM-010 is DAG-runnable and does not wait on MM-009. MM-009 reached PASS at
  `4c2ffd9` while this package was in progress; that pass_record was not edited.
- Only MM-010 was implemented. MM-011 and later packages were not changed.
- Primary scopes: `module.rights`, `module.provenance`.
- Manifest/evidence bookkeeping is under non-fingerprinted `global.manifest`.
- No schema, migration, SQLite table, ChangeSet op, EVENT_TYPE, prior-package
  source, gate, toolchain, `pyproject.toml`, or `tests/__init__.py` file was
  changed. MM-009 owned files were not touched.

## Implementation

- `movie_muse.rights.api` is the rights public surface. `RightsService`
  registers sources (license, permitted uses, classification, expiry), stores
  immutable source versions in content-addressed blobs plus
  `rights.index_digest`, and fail-closes unlicensed/disallowed/expired/
  unvalidated use with `UnlicensedSourceError` or `PermittedUseDeniedError`.
- Human owner/administrator (`Action.VIEW_RIGHTS`) registrations are
  human-validated. Integration `PROPOSE` records stay candidate until a human
  with `VIEW_RIGHTS` validates. Integration principals cannot validate.
  Producer/writer/director/viewer cannot manage the registry or export
  disclosures (`VIEW_RIGHTS` denied for producer).
- `movie_muse.provenance.api` is the provenance public surface.
  `ProvenanceService` / `EvidenceBundleService` builds an `EvidenceBundle`
  that requires at least one permitted citation, attaches `MethodProvenance`
  (provider, model version, prompt version, policy version, timestamp;
  compatible with MM-009 `ModelProvenance` mappings without importing
  `model_router` internals), records input lineage (source / revision /
  artifact-version ids), and stores uncertainty, alternatives, and
  counter-evidence.
- Payloads containing `chain_of_thought` / `chain-of-thought` / `<thinking>`
  are rejected. Public views and export disclosures never include or claim to
  expose private chain-of-thought.
- Forecasts are labeled scenarios, not guarantees. Synthetic audiences are
  labeled hypotheses, not human samples.
- Export disclosures require `VIEW_RIGHTS` and fail closed if any cited source
  is unlicensed or no longer permitted for export. Bundles may *link* to the
  generic artifact subsystem via `artifacts.api` without a parallel artifact
  store.
- Index updates use `workspace.store.transaction()` (`BEGIN IMMEDIATE`)
  load-modify-commit. `AuditLog.append` / `authorize(audit=True)` run outside
  the open transaction. Source ids use `src_{ulid}`; rights records and
  evidence bundles use `new_id("rights_record")` / `new_id("evidence_bundle")`.
- Offline/airplane operation uses only local persistence. No new SQLite tables.

## Commits

- `7ef3c92952874683b0e6e2cb4aaff675c356c3b7` — implement rights registry,
  provenance/Evidence Bundles, tests, and IN_PROGRESS bookkeeping.
- This evidence commit is separate and does not change fingerprinted owned
  paths.

## Exact quality commands and results

Full output is in `quality-commands.txt`. Captured at implementation commit
`7ef3c92952874683b0e6e2cb4aaff675c356c3b7` on 2026-09-01T16:31:50Z–16:33:02Z.

- `python3 scripts/validate_handoff.py` — exit 0,
  `HANDOFF_VALIDATION=PASS`.
- `python3 -m ruff check src tests scripts backend` — exit 0, all checks passed.
- `python3 -m mypy src` — exit 0, no issues in 132 source files.
- `PYTHONPATH=src python3 -m pytest tests/rights tests/provenance -q` — exit 0,
  30 passed.
- `PYTHONPATH=src python3 -m pytest tests/rights tests/provenance tests/authorization tests/artifacts tests/audit -q`
  — exit 0, 79 passed.
- `PYTHONPATH=src python3 -m pytest` — exit 0, 423 passed, one pre-existing
  HTTPX deprecation warning.
- `PYTHONPATH=src python3 scripts/mm_status.py validate` — exit 0,
  `STATUS_VALIDATE=PASS`.
- `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` — exit 0,
  `SCOPE_COVERAGE=PASS`.
- `PYTHONPATH=src python3 scripts/mm_status.py runnable` — exit 0; MM-010 and
  MM-011 listed.
- `PYTHONPATH=src python3 scripts/mm_status.py boundaries` — exit 0,
  zero violations.
- `PYTHONPATH=src python3 scripts/mm_status.py secrets` — exit 0, zero hits.
- `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-010` — exit 0;
  at `7ef3c92`, fingerprint
  `31cf080db2d8ef8215b90fb221f784211abd2c232d966a31a83270360c6a2dbe`.
- `./scripts/verify_all.sh` — exit 1 as designed:
  `MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY
  missing_executable_gate=migrations_backup_and_recovery`.

## Evidence and tests

- `evidence/MM-010/COMMANDS.md`
- `evidence/MM-010/quality-commands.txt`
- `tests/rights/test_registry_and_permitted_use.py`
- `tests/rights/test_acl_and_concurrency.py`
- `tests/rights/test_rights_boundaries.py`
- `tests/provenance/test_evidence_bundles.py`
- `tests/provenance/test_export_and_honesty.py`
- `tests/provenance/test_provenance_boundaries.py`

## Known limitations

- `verify_all.sh` remains intentionally fail-closed because the later
  `migrations_backup_and_recovery` gate is absent. That is an expected
  limitation, not a PASS waiver. Adding that gate is outside MM-010.
- Specialized export packets link to the generic artifact lifecycle; PDF/deck
  rendering belongs to later packages.
- The full test suite has one unrelated HTTPX deprecation warning.

## Required external gates

None new for MM-010.

## Independent verifier instructions

1. Use a clean detached checkout of implementation commit
   `7ef3c92952874683b0e6e2cb4aaff675c356c3b7` (or this evidence commit).
   Confirm MM-002/MM-004/MM-006/MM-007 are current PASS, MM-010 is
   IN_PROGRESS with `pass_record: null`, and do not edit the canonical ledger
   or MM-009 owned files.
2. Recompute
   `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-010` at that
   HEAD. At implementation commit `7ef3c92`, the expected fingerprint is
   `31cf080db2d8ef8215b90fb221f784211abd2c232d966a31a83270360c6a2dbe`.
   An evidence-only commit changes hashed `verification_commit` while
   fingerprinted owned/shared paths remain unchanged.
3. Run every exact quality command in the prior section. Do not treat the
   expected `verify_all.sh` NOT_READY result as a waiver or as full completion.
4. Register an unlicensed or disallowed source as owner; `require_permitted_use`
   and export disclosure must raise `UnlicensedSourceError`.
5. Invite a producer. `VIEW_RIGHTS`, `register_source`, and export disclosure
   must be denied. Owner register + export must succeed and include license
   plus human-validation state.
6. `build_bundle` with zero citations must fail. A payload containing
   `chain_of_thought` must be rejected. Public view/export JSON must not
   include that field or claim to expose hidden chain-of-thought.
7. An integration-proposed licensed source must not be citable until a human
   with `VIEW_RIGHTS` validates it. The integration principal must not be able
   to validate the source or the bundle.
8. Two LocalWorkspace connections, two-party barrier, concurrent
   `register_source`; both succeed with distinct ids; list retains both.
   Confirm index writes use `BEGIN IMMEDIATE` and add no SQLite tables.
9. Airplane/auth/subscription outage must still allow local register, cite,
   bundle build, and owner export.
10. Forecast bundles must carry the scenario disclaimer; synthetic-audience
    bundles must carry the hypothesis disclaimer. Neither may present as a
    human sample or guarantee.
11. After a bundle is built, remove `export_disclosure` from the source's
    permitted uses and confirm bundle export fails closed.
12. Do not mark PASS unless independent verification succeeds and the
    orchestrator records a committed pass record.
