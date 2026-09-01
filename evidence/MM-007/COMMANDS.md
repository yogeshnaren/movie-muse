# MM-007 — Generic artifact subsystem — implementer evidence

Item: MM-007  
Role: implementer. This record is not a PASS record and does not populate
`items.MM-007.pass_record`. An independent verifier must reproduce the work.

## Dependency and scope confirmation

- MM-002, MM-004, MM-005, and MM-006 were current PASS before work.
- `PYTHONPATH=src python3 scripts/mm_status.py runnable` listed MM-007 and MM-008.
- Only MM-007 was implemented. MM-008 and later packages were not changed.
- Primary scope: `module.artifacts`.
- Manifest/evidence bookkeeping is under non-fingerprinted `global.manifest`.
- No schema, migration, SQLite table, prior-package source, gate, toolchain, or
  release-test file was changed.

## Implementation

- `movie_muse.artifacts.api` is the only public module surface.
- `ArtifactService` supports document, table, media, and package artifacts with
  the same content-addressed blob/index storage and lifecycle.
- MM-002 `Artifact`, `ArtifactVersion`, and `ArtifactStatus` are reused.
  Module-owned immutable types model `ArtifactTemplate`, `ArtifactRender`,
  `ArtifactLink`, `DeliveryRecord`, review history, classification, and the
  immutable input record.
- `artifacts.index_digest` in `workspace_meta` addresses all module records.
  Render bytes are content-addressed blobs. No specialized paths or new SQL
  tables exist.
- Artifact creation calls `AuthorizationService.declare_artifact`; every public
  operation checks project/artifact ACL through public authorization APIs.
- Version content, canonical inputs, source revision, template/version,
  renderer version, evidence ids, rights ids, creator/editor, classification,
  draft status, and checksum are immutable. `update_version` and
  `delete_version` fail. Changes and regeneration create new ids.
- Rendering is canonical JSON over artifact type, template, renderer version,
  immutable inputs, source revision id, and source payload. Re-rendering and
  unchanged regeneration produce identical bytes/checksums.
- Review transitions are append-only: `draft -> in_review ->
  approved|archived`, with approved versions optionally archivable later.
  Approval/archive requires `Action.ACCEPT` and a human principal. The
  immutable generated `ArtifactVersion` remains draft; the current status is
  projected from review records.
- Investor listing returns approved versions only.
- Preview persists a checksum-bound `ArtifactRender` without delivery. Delivery
  requires `Action.EXPORT`, a matching preview id/checksum, and explicit
  `confirm=True`. It creates and audits a `DeliveryRecord` but deliberately
  performs no network send.
- Export requires `Action.EXPORT`, deterministically re-renders, and writes the
  exact bytes to the caller-selected filesystem path.
- Revision links validate the source through `RevisionService`. Unknown
  artifacts, versions, templates, revisions, principals, and unconfirmed or
  mismatched delivery fail closed.
- Offline/airplane operation uses only local persistence, revisions,
  authorization, and audit services.

## Commits and test correction

- `6f1e5548b09a94be9343a576b0b0924ce73ce209` — implement generic artifact
  subsystem, tests, and IN_PROGRESS bookkeeping.
- `1c0f96fa8d0f73bb4e711e141b96f32abf52801d` — preserve nested immutable
  inputs when regenerating/re-rendering.
- `52ccb97651cc3805540e1168a9b6889a0200aea5` — bind immutable-operation
  rejection and editor attribution to the authorized acting principal.

The first focused run at `6f1e554` had 12 passing and 2 failing parametrized
render cases. Runtime evidence showed nested `mappingproxy` values reaching
the JSON encoder. The follow-up converts the immutable projection back from
its stored canonical JSON only at the render boundary. All 14 focused tests
then passed.

## Exact quality commands and results

Full output summary is in `quality-commands.txt`.

- `python3 scripts/validate_handoff.py` — exit 0,
  `HANDOFF_VALIDATION=PASS`.
- `python3 -m ruff check src tests scripts backend` — exit 0, all checks passed.
- `python3 -m mypy src` — exit 0, no issues in 97 source files.
- `PYTHONPATH=src python3 -m pytest tests/artifacts -q` — exit 0, 14 passed.
- `PYTHONPATH=src python3 -m pytest tests/artifacts tests/authorization tests/revisions tests/persistence -q`
  — exit 0, 75 passed.
- `PYTHONPATH=src python3 -m pytest` — exit 0, 338 passed, one pre-existing
  HTTPX deprecation warning.
- `PYTHONPATH=src python3 scripts/mm_status.py validate` — exit 0,
  `STATUS_VALIDATE=PASS`.
- `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` — exit 0,
  `SCOPE_COVERAGE=PASS`.
- `PYTHONPATH=src python3 scripts/mm_status.py runnable` — exit 0; MM-007 and
  MM-008 listed.
- `PYTHONPATH=src python3 scripts/mm_status.py boundaries` — exit 0,
  zero violations.
- `PYTHONPATH=src python3 scripts/mm_status.py secrets` — exit 0, zero hits.
- `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-007` — exit 0;
  at `52ccb97`, fingerprint
  `98b6523c634e857a93fa17d1dde72d907e9c4171147d38ed222d73b059e35c80`.
- `./scripts/verify_all.sh` — exit 1 as designed:
  `MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY
  missing_executable_gate=migrations_backup_and_recovery`.

## Evidence and tests

- `evidence/MM-007/COMMANDS.md`
- `evidence/MM-007/quality-commands.txt`
- `tests/artifacts/test_artifact_lifecycle.py`
- `tests/artifacts/test_review_delivery_and_acl.py`
- `tests/artifacts/test_regeneration_and_boundaries.py`
- `tests/artifacts/conftest.py`
- `evidence/secret-scan.txt`

## Known limitations

- The generic renderer emits a deterministic Movie Muse JSON render envelope.
  PDF, FDX, image/video codecs, and specialized artifact presentation belong
  to later packages and can reuse this lifecycle.
- Delivery records an explicitly confirmed, audited delivery intent and never
  sends over a network. Real delivery-channel integration belongs to MM-036.
- `verify_all.sh` remains intentionally fail-closed because the later
  `migrations_backup_and_recovery` gate is absent. Adding that gate is outside
  MM-007 and would change forbidden earlier-package scope.
- The full test suite has one unrelated HTTPX deprecation warning.

## Required external gates

None for MM-007.

## Independent verifier instructions

1. Use a clean detached checkout containing commits `6f1e554`, `1c0f96f`, and
   `52ccb97`.
   Confirm MM-002/MM-004/MM-005/MM-006 are current PASS, MM-007 is
   IN_PROGRESS with `pass_record: null`, and no other status changed.
2. Recompute
   `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-007` at the
   checkout HEAD. At implementation commit `52ccb97`, the expected fingerprint
   is `98b6523c634e857a93fa17d1dde72d907e9c4171147d38ed222d73b059e35c80`.
   An evidence-only commit changes the hashed verification commit, while
   fingerprinted owned/shared paths remain unchanged.
3. Run every exact quality command in the prior section. Do not treat the
   expected `verify_all.sh` NOT_READY result as a waiver or as full completion.
4. Probe immutable versions: mutate the caller input after generation, attempt
   nested input assignment, `update_version`, and `delete_version`; stored
   inputs/checksum must remain unchanged and all rewrite/delete attempts fail.
5. Create document, table, media, and package artifacts. Confirm all four are
   indexed under the same `artifacts.index_digest`, use the same template,
   version/review/render/link lifecycle, and create no SQL tables.
6. Render one version repeatedly and regenerate it against the same source.
   Bytes/checksums must match exactly while version ids differ.
7. Preview a version, then call delivery as owner with `confirm=False`.
   It must fail and write no `DeliveryRecord`. A viewer must fail export and
   confirmed delivery. Owner delivery with matching preview plus
   `confirm=True` must append exactly one local record and an
   `artifact_delivery_confirmed` audit record with `network_sent=False`.
8. Confirm a generated version is draft, direct draft-to-approved fails, and
   investor listing hides it. Submit for review and explicitly approve as an
   authorized human; only then may investor listing include it.
9. After artifact creation, authorize `READ` on its artifact id and expect
   allow. Authorize an undeclared artifact id in the same project and expect
   `unknown_resource`.
10. Regenerate unchanged inputs against a newly saved source revision. The new
    version must have a different checksum and remain draft; compare must report
    source/checksum changed and inputs unchanged.
11. Verify unknown source revision/template/version and airplane-mode behavior,
    plus the AST/public-boundary test preventing imports of sibling internals.
12. Do not mark PASS unless independent verification succeeds and the
    orchestrator records a committed pass record.
