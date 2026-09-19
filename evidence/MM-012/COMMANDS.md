# MM-012 — Golden fixtures and test harness — implementer evidence

Item: MM-012
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-012.pass_record.

## Scope

`scope_keys: [test.fixtures, test.harness]`
- `fixtures/**` (screenplay fixtures, rights, recordings, bench, golden-path seed)
- `tests/fixtures/**`
- `tests/harness/**`
- `src/movie_muse/testkit/**` public `movie_muse.testkit.api`

Did not edit MM-001 through MM-011 owned implementation files except MM-012
IN_PROGRESS bookkeeping (`movie_muse_build_status.yaml`, `docs/working-log.md`).
Did not implement MM-013 or later. Did not mark PASS. Did not overwrite
`tests/schemas/fixtures/**`.

## What was built

1. **Screenplay fixtures** under `fixtures/screenplays/{small_kitchen,
   feature_complete_harbor, production_locked_sides, adversarial_unicode_rtl}/`
   each with `document.json` (canonical ScreenplayDocument), `LICENSE.md`,
   `rights.yaml`, `MANIFEST.yaml`, and `expected/{ast,layout,film_ir}.json`.
2. **AST goldens** are real document-kernel dumps (normalize + structural
   facts) and are compared. Layout/FilmIR goldens are typed deferred records
   (`awaiting: MM-014` / `MM-018`) that are disclosed, not `pytest.skip`.
   Marking them current without a known producer fails closed.
3. **GoldenRegistry** refuses overwrite without `approve_golden_update(...)`.
4. **NondeterminismGuard** hashes load/AST N times and fails on mismatch.
5. **Provider recordings** under `fixtures/recordings/` load into
   `AdapterResult` doubles. No live providers. EXT-REMOTE-MODEL untouched.
6. **Rights fixtures** plus golden-path seed
   `load_golden_path_project(workspace)`: airplane-mode LocalWorkspace,
   feature-complete document, revision head, licensed+unlicensed sources,
   tiny dependency graph. Unlicensed use raises `UnlicensedSourceError`.
7. **MovieMuse Bench**: `TaskConfiguration` identity is model + prompt +
   context strategy + tools + decoding + schema. Three families
   (objective ground truth, blinded human preference, observed workflow
   utility). `collapse_to_universal_score()` raises. No MovieMuseScore.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`0fe55bcff33032286dd1a52098696e61e029a755`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: 156 source files |
| `PYTHONPATH=src python3 -m pytest tests/fixtures tests/harness -q` | 17 passed |
| `PYTHONPATH=src python3 -m pytest tests/fixtures tests/harness tests/document tests/revisions tests/rights tests/dependencies -q` | 99 passed |
| `PYTHONPATH=src python3 -m pytest` | 465 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-012` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-012` | `2f1c7e594ba843ab485a9904ecf66795d38fdfb5e9f229f5f1fb12de55b9fa3d` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `0fe55bcff33032286dd1a52098696e61e029a755`
Input fingerprint at `0fe55bc`: `2f1c7e594ba843ab485a9904ecf66795d38fdfb5e9f229f5f1fb12de55b9fa3d`
UTC: `2026-09-01T17:38:28Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-012` at
the evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- Layout and FilmIR goldens are deferred until MM-014 / MM-018. AST, rights,
  seed, recordings, and bench families are required and were not skipped.
- `movie_muse.testkit` is not listed in MM-001-owned
  `config/module-layout.yaml` so MM-001 PASS is not invalidated. Public
  surface remains `movie_muse.testkit.api`; cross-module imports still go
  through `*.api`.
- Fine-tuning is out of scope. Synthetic audiences are labeled hypotheses.
- `verify_all.sh` remains fail-closed until later packages add named gates.

## Required external gates

None new for MM-012. Did not mark EXT-REMOTE-MODEL.

## Verifier instructions

1. Fresh detached checkout of `0fe55bcff33032286dd1a52098696e61e029a755` or
   this evidence commit. Recompute fingerprint MM-012 at that HEAD. At
   `0fe55bc` it must be
   `2f1c7e594ba843ab485a9904ecf66795d38fdfb5e9f229f5f1fb12de55b9fa3d`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-011 are current PASS and MM-012 is IN_PROGRESS
   with `pass_record: null`.
3. Run ruff, mypy src, focused pytest (`tests/fixtures tests/harness`),
   affected (`tests/document tests/revisions tests/rights tests/dependencies`),
   and full pytest (465).
4. Probes:
   - Every fixture directory has LICENSE.md + rights.yaml with license and
     consent; `allow_training` is false.
   - Catalog lists all four classes; `REQUIRED_PRODUCTION_EDGES` are covered
     across the set.
   - Live AST digest matches committed `expected/ast.json`; five-run
     NondeterminismGuard is stable.
   - Unapproved golden overwrite raises `UnapprovedGoldenUpdateError`.
   - Layout/FilmIR `assert_expected_available` returns deferred records;
     current-without-producer fails closed; no pytest.skip of required checks.
   - Bench configuration identity differs when only prompt/context/tools
     change under the same model brand; `collapse_to_universal_score` raises;
     preference labels are blinded configuration ids.
   - `load_golden_path_project` works with airplane mode; unlicensed source
     is blocked by `RightsService.require_permitted_use`.
   - Recordings have `live: false` / `network: false` and load as
     `AdapterResult`.
5. Do not treat this implementer record as PASS.
