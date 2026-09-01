# MM-002 — Domain constitution and versioned schemas — implementer evidence

Item: MM-002
Role: implementer (`movie-muse-implementer`). This record is NOT a PASS record and
does not set `movie_muse_build_status.yaml` items.MM-002.pass_record. Only an
independent verifier may do that.

## Scope

`scope_keys: [domain.schemas]`, owning:
- `src/movie_muse/schemas/**`
- `schemas/domain/**`
- `tests/schemas/**`
(shared with `schemas/build-status.schema.json`; shared-by, not owned-by, later
modules `module.document` (MM-003), `module.persistence` (MM-004),
`module.identity`.)

## What was built

1. **Versioned JSON Schemas (Draft 2020-12)** under `schemas/domain/*.schema.json`
   for all 16+ required entities: `project`, `screenplay_document`,
   `film_ir`, `creative_intent_ir`, `project_memory`, `proposal`, `change_set`,
   `project_event`, `evidence_bundle`, `rights_record`, `collaboration_event`,
   `shot_ir`, `scene_space`, `production_projection`, `scenario_model`,
   `artifact` + `artifact_version`, `dependency_node`, plus the 5 epistemic-type
   schemas (`epistemic_authored_fact`, `epistemic_structural_fact`,
   `epistemic_inferred_claim`, `epistemic_operational_assumption`,
   `epistemic_scenario_output`) and a shared `common.schema.json` with reusable
   `$defs` (schema_version, timestamp, epistemic level, compatibility kind,
   percentile, and every stable-ID pattern).
2. **Hand-written Python types** under `src/movie_muse/schemas/` mirroring every
   schema as frozen `@dataclass` types, each with `from_dict`/`to_dict`
   round-tripping and constructor-time validation (`__post_init__`).
3. **Epistemic type separation** (`epistemic.py` + 5 schemas): `AuthoredFact`,
   `StructuralFact`, `InferredClaim`, `OperationalAssumption`, `ScenarioOutput`
   are five distinct dataclasses (not a shared base with a `kind` flag consumers
   could spoof); each has a `ClassVar` binding to its `EpistemicLevel`. Runtime
   proof of non-interchangeability is in `tests/schemas/test_epistemic_validation.py`
   (cross-kind payloads rejected by `jsonschema` `const` on `kind` plus per-kind
   required provenance fields) and static proof in
   `tests/schemas/typecheck_fixtures/invalid_epistemic_promotion.py` (asserted to
   fail `mypy`).
4. **Stable ID system** (`ids.py`): kind-prefixed ULIDs (`new_id(kind)`,
   `is_valid_id`, `parse_id_kind`, `require_id`) plus `NewType` aliases per kind
   (document, sequence, block, inline span, scene, character cue, dialogue pair,
   note, revision mark, production tag, attachment, and all other entity IDs).
   Prefix table is asserted consistent with the regex patterns in
   `common.schema.json` (`tests/schemas/test_ids.py`).
5. **Compatibility policy + migrations**: `compatibility.py` classifies schema
   diffs as `Additive`/`Breaking`; `migrations.py` implements a
   `MigrationRegistry` with a `migrate(from, to)` interface, chained multi-step
   migration resolution, cycle detection, and two real registered migrations
   (`rights_record` 1.0→1.1, `collaboration_event` 1.0→1.1). Tests:
   `test_compatibility.py`, `test_migrations.py`.
5. **Fixtures**: every one of the 23 domain schemas + 5 epistemic schemas has a
   `tests/schemas/fixtures/<name>/valid.json` and `.../invalid.json`, all
   self-validated by `tests/schemas/test_fixtures.py` (valid passes,
   invalid raises `jsonschema.ValidationError`; a coverage test asserts all
   required schema names are present).
6. **Module boundary test**: `tests/schemas/test_boundaries.py` reuses
   `movie_muse.toolchain.boundaries.scan_file` to assert other modules may
   import `movie_muse.schemas.api` but are rejected for any
   `movie_muse.schemas.<internal_module>` import.
7. **`ScreenplayDocument`** (`document.py` + `screenplay_document.schema.json`):
   typed tree of `Sequence` → `Block` (`BlockKind` enum with the required
   minimum set: SceneHeading, Action, Character, Parenthetical, Dialogue,
   Transition, Shot, General, Lyrics, PageBreak, TitlePageElement) with
   `InlineSpan`, `Note`, `RevisionMark`, `ProductionTag`, `Attachment` and
   stable-ID cross-reference validation.
8. **`ProjectEvent`** (`events.py`): immutable command→event record with
   `project_id`, `branch_id`, `base_revision_id`, `result_revision_id`,
   `actor_id`, `command_id`/`operation_id`, `schema_version`,
   `causal_id`/`correlation_id`, and a computed `integrity_hash` (rejects
   tampering, unknown event types).
9. **`Proposal`** (`proposal.py`): immutable candidate `ChangeSet` against
   `base_revision_id`, with `ImpactSummary`, `RevalidationRecord`, and
   validation that its `change_set.base_revision_id` matches `base_revision_id`.
10. **Public surface**: `src/movie_muse/schemas/api.py` re-exports every public
    type/function; all internal modules (`document.py`, `events.py`, etc.) are
    plain submodules of `movie_muse.schemas`, and `test_boundaries.py` +
    `mm_status.py boundaries` confirm nothing outside `movie_muse.schemas`
    imports them directly.

## Commands run and results

See `quality-commands.txt` (summary) and `quality-commands.log` (full captured
output) in this directory. Headline results:

| Command | Result |
|---|---|
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy` | Success: no issues found in 35 source files |
| `python3 -m pytest tests/schemas -v` | 172 passed |
| `python3 -m pytest` (full suite) | 192 passed, 3 pre-existing failures (see below) |
| `python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `python3 scripts/mm_status.py runnable` | `{"runnable": ["MM-002"]}` |
| `python3 scripts/mm_status.py boundaries` | `{"count": 0, "violations": []}` |
| `python3 scripts/mm_status.py secrets` | `{"count": 0, "hits": []}` |

## Known limitation (pre-existing, out of MM-002 scope)

Three tests fail, and were confirmed (via `git stash`) to already fail at branch
HEAD `b73668852f98ff06c3565169088cbed19f9bfb54`, i.e. before any MM-002 file
existed:

- `tests/toolchain/test_status_tool.py::test_only_mm001_is_runnable_at_baseline`
- `tests/toolchain/test_status_tool.py::test_mm001_change_does_not_stale_unstarted_dependents`
- `tests/release/test_verify_all_fail_closed.py::test_verify_all_stays_fail_closed_until_all_gates_exist`

Root cause: these tests hard-code the assumption that MM-002 is `NOT_STARTED`
and not runnable. `movie_muse_build_status.yaml` was moved to
`MM-002: IN_PROGRESS` by the orchestrator in the prior commit
(`b736688`, "Start MM-002 domain constitution after MM-001 PASS"), before this
implementation task began. These tests are `global.toolchain`/`global.ci`-scoped
(owned by MM-001, currently PASS); MM-002's `scope_keys` is only
`[domain.schemas]`, so an MM-002 implementer must not edit MM-001-owned test
files or MM-001's `pass_record`. `./scripts/verify_all.sh` and
`./scripts/gates/static_quality_and_boundaries.sh` therefore still fail-closed
(never print the PASS sentinel), just at this pre-existing baseline-assumption
gap rather than a missing-gate check. Documented in `docs/working-log.md` and
flagged for a follow-up MM-001-scoped fix independent of this package.

## Fingerprint

Computed with `python3 scripts/mm_status.py fingerprint MM-002` after commit
(see final report for the exact hash bound to the committed SHA — fingerprints
are commit-bound, see `src/movie_muse/toolchain/fingerprint.py`).

## Verifier instructions

1. Fresh clone/checkout of this branch at the recorded commit SHA.
2. `export PYTHONPATH=src`
3. Run: `python3 -m ruff check src tests scripts backend`
4. Run: `python3 -m mypy`
5. Run: `python3 -m pytest tests/schemas -v` (expect 172 passed)
6. Run: `python3 -m pytest` (expect 192 passed, 3 pre-existing/out-of-scope
   failures listed above — verify they are identical to the ones listed, not new)
7. Run: `python3 scripts/mm_status.py validate`
8. Run: `python3 scripts/mm_status.py check-scopes`
9. Run: `python3 scripts/mm_status.py boundaries` (expect 0 violations)
10. Run: `python3 scripts/mm_status.py secrets` (expect 0 hits)
11. Run: `python3 scripts/mm_status.py fingerprint MM-002` and confirm the hash
    is reproducible against the committed tree.
12. Independently review each acceptance criterion (1–10 in the task) against
    the files listed in "What was built" above and the fixtures/tests in
    `tests/schemas/`.
13. Do NOT set `pass_record` without reproducing all of the above on a clean
    environment.
