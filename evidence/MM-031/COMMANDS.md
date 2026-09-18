# MM-031 — Director Mode, DirectorVisionGraph, and ShotIR — implementer evidence

Item: MM-031
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.director, module.shot_ir]`
- `src/movie_muse/director/**`
- `tests/director/**`
- `src/movie_muse/shot_ir/**`
- `tests/shot_ir/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`DirectorVisionService` owns deterministic SceneSpace geometry and blocking,
coverage, producer constraints, and role-specific semantic annotations that
transfer across pages by stable anchor token. Generation defaults to disabled.
`ShotIRService` owns provider-independent shots (camera, composition, eyelines,
light, performance/color intent), locked attributes, and diagrammatic shot
cards that never call a model. Scene and intent change notifications stale
affected derived shot nodes.

## Commands

See `quality-commands.txt`. Headline: 15 focused tests passed; full pytest
749 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T23:50:48Z`
SHA: `6fbe904eea433343a1e0710b12ccc25a32b967b8`
fingerprint: `d19306d6f91c44e7edd506f64c992e5ffd5b08c3a2db99496c6fc0eb3317f8b1`

## Known limitations

- Image/video rendering is MM-032/MM-034; this package only defines ShotIR.
- `verify_all.sh` remains fail-closed until later named gates exist.
