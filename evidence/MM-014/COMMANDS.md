# MM-014 — Deterministic layout, pagination, and production revisions — implementer evidence

Item: MM-014
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-014.pass_record.

## Scope

`scope_keys: [module.layout, module.production_revisions, test.render]`
- `src/movie_muse/layout/**` public `movie_muse.layout.api`
- `src/movie_muse/production_revisions/**` public `movie_muse.production_revisions.api`
- `tests/layout/**`, `tests/production_revisions/**`, `tests/render/**`

Did not add `layout` or `production_revisions` to MM-001-owned
`config/module-layout.yaml`. Did not add `fixtures/render` (would STALE
MM-012). Did not implement MM-015 or later. Did not mark PASS.

## What was built

1. **Pinned layout engine** `1.0.0` with Courier Prime 10-pitch / 6 LPI
   metrics (`courier-prime-10cpi-v1`). Layout is a pure function of
   document + style + paper + lock state + engine version. Identical
   inputs produce identical `input_hash` / `layout_hash`.
2. **Pagination**: US Letter / A4 profiles, title pages, headers/footers,
   MORE/CONT'D dialogue splits, dual-dialogue columns, omitted-scene
   occupancy, forced page breaks, A/B overflow when a reserved page is
   next.
3. **Locks**: `ProductionLockState` is an input. Assigned page extras are
   honored only when `pages_locked`. Unlock/repagination is
   `ProductionRevisionService.unlock_repagination` and requires
   `Action.MANAGE_PRODUCTION_LOCKS`. The recorded event is the closed
   `ProductionRequirementConfirmed` type.
4. **Production overlays**: changed pages, A/B scene labels, omitted
   scene ids, sides packets (`new_id("artifact")`), clean vs revision
   export. Overlays do not rewrite ScreenplayDocument canon.
5. **Render traces**: structured grid / reading-order text. Zero-loss
   fields have tolerance 0. `RASTER_PIXEL_TOLERANCE` is documented for a
   later bitmap renderer and does not weaken traces.

## FDX guard

`tests/fdx/test_profile_coverage.py` still forbids FDX from skipping or
inventing `layout_hash` / importing `movie_muse.layout`. The old
"layout directory must not exist" assertion was replaced so MM-014 can
exist. That file is owned by `test.fdx`, so **MM-013 is STALE** and must
be independently re-verified before MM-014 can be recorded PASS.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`d583fa21abc48984ba41e3c93cd161a1f6eee8b7`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: 182 source files |
| `PYTHONPATH=src python3 -m pytest tests/layout tests/production_revisions tests/render -q` | 24 passed |
| `PYTHONPATH=src python3 -m pytest tests/layout tests/production_revisions tests/render tests/fdx tests/document tests/revisions --tb=no` | 92 passed |
| `PYTHONPATH=src python3 -m pytest --tb=no` | 515 collected / 515 passed, 2 warnings |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-013` (MM-014 blocked until MM-013 re-PASS) |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-013` | `0509a894c5363d0008dc1da69cb0a2351238371b301edebc521a08f0a30ad261` |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-014` | `9829c3ec46a77531aee1b292505a2fbaae807b1487f952fdd8ca6a2754cd183a` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `d583fa21abc48984ba41e3c93cd161a1f6eee8b7`
UTC: `2026-09-05T23:08:00Z`

An evidence-only follow-up commit changes HEAD, so fingerprints at the
evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Layout goldens under `fixtures/screenplays/*/expected/layout.json`
  remain deferred (`awaiting: MM-014` placeholders). This package
  produces live layout hashes; filling those MM-012 goldens as CURRENT
  would STALE MM-012 and was not done.
- Pixel/bitmap renders are not implemented. Trace and grid comparison
  is the reference.
- `EXT-FDX-FINAL-DRAFT` stays `NOT_RUN`.
- MM-013 must be independently re-verified before MM-014 PASS.

## Required external gates

None owned by MM-014. `EXT-FDX-FINAL-DRAFT` remains `NOT_RUN`.
