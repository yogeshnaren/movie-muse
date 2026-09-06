# MM-002 — Domain constitution and versioned schemas — implementer evidence

Item: MM-002
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-002.pass_record. Only an independent
verifier may do that.

## Scope

`scope_keys: [domain.schemas]`, owning:
- `src/movie_muse/schemas/**`
- `schemas/domain/**`
- `tests/schemas/**`

## What was built

1. Versioned JSON Schemas (Draft 2020-12) under `schemas/domain/*.schema.json`
   for every required domain type, including the five non-interchangeable
   epistemic levels.
2. Frozen Python dataclasses under `src/movie_muse/schemas/` with public surface
   `movie_muse.schemas.api`. Nested JSON-like fields are recursively frozen by
   `@sealed` (wraps generated `__init__` so types without `__post_init__` still
   freeze mappings/lists).
3. Epistemic type separation: distinct dataclasses, JSON Schema `kind` consts,
   constructor kind checks, and mypy fixtures that reject silent promotion.
4. Stable kind-prefixed ULID IDs.
5. Compatibility policy (`Additive`/`Breaking`) and `MigrationRegistry` with
   real 1.0→1.1 hooks for `rights_record` and `collaboration_event`.
6. Valid/invalid fixtures for every domain schema.
7. Module-boundary tests: other modules may import `movie_muse.schemas.api` only.
8. `ScreenplayDocument` typed block tree with the architecture minimum block set.
9. Immutable `ProjectEvent` with integrity hash; `Proposal`/`ChangeSet` with
   matching `base_revision_id` and frozen nested payloads.
10. Recursive immutability for `Block.unknown_extensions`, epistemic `value`,
    `ProductionProjection.data`, changeset/event payloads.

## Commands run and results

See `quality-commands.txt` in this directory. Headline results at this
implementation revision:

| Command | Result |
|---|---|
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy` | Success: no issues found in 35 source files |
| `python3 -m pytest tests/schemas -q` | 188 passed |
| `python3 -m pytest` | 212 passed, 1 warning |
| `python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `python3 scripts/mm_status.py runnable` | `{"runnable": ["MM-002"]}` |
| `python3 scripts/mm_status.py boundaries` | `{"count": 0, "violations": []}` |
| `python3 scripts/mm_status.py secrets` | `{"count": 0, "hits": []}` |

`./scripts/verify_all.sh` remains fail-closed (`NOT_READY` for later package
gates such as `migrations_backup_and_recovery`). That is required until those
packages exist; it is not an MM-002 acceptance waiver.

## Verifier instructions

1. Fresh clone/checkout of this branch at the recorded commit SHA.
2. `export PYTHONPATH=src`
3. Run: `python3 -m ruff check src tests scripts backend`
4. Run: `python3 -m mypy`
5. Run: `python3 -m pytest tests/schemas -q` (expect all passed)
6. Run: `python3 -m pytest` (expect all passed)
7. Run: `python3 scripts/mm_status.py validate`
8. Run: `python3 scripts/mm_status.py check-scopes`
9. Run: `python3 scripts/mm_status.py boundaries` (expect 0 violations)
10. Run: `python3 scripts/mm_status.py secrets` (expect 0 hits)
11. Run: `python3 scripts/mm_status.py fingerprint MM-002` and confirm the hash
    is reproducible against the committed tree.
12. Independently review MM-002 acceptance: versioned schemas, valid/invalid
    fixtures, compatibility policy, migration hooks, stable IDs, generated
    types tested across application boundaries, epistemic non-interchangeability,
    and recursive immutability of nested JSON-like fields.
13. Probe nested mutation of `Block.unknown_extensions`, `AuthoredFact.value`,
    `ProductionProjection.data`, and event/changeset payloads. PASS only if
    nested mutation raises and integrity hashes cannot go stale.
14. Probe compatibility: narrowing an existing enum (and const/`$ref`/pattern/
    bounds/nested-schema edits) must be BREAKING; adding an optional property
    remains additive.
15. Do NOT set `pass_record` in this checkout; return PASS/FAIL for the
    orchestrator to record.
