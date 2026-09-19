# MM-037 — Scheduling and constraint engine — implementer evidence

Item: MM-037
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.scheduling]`
- `src/movie_muse/scheduling/**`
- `tests/scheduling/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`ScheduleService` compiles deterministic seeded boards and strips from a
locked breakdown: scene durations, day/night, company moves, cast/location
availability, labor/rest, and stunt/minor safety. Hard constraints never
place an invalid strip; manual moves that would break them raise
`InfeasibleScheduleError` with an explanation. Alternatives are inspectable
scenarios and do not replace canon. Pins survive recompile. Breakdown
changes label affected schedules stale and block current export.

## Commands

See `quality-commands.txt`. Headline: 13 focused tests passed; full pytest
792 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T01:01:20Z`
SHA: `fcdff62223ee344545abf7b8eb9f139720ca9d46`
fingerprint: `c1fa7e64fa1fb6a4ba3a42cdbb5dd678ddb70be37b5c898cb2c93753785bd18b`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Packing is a deterministic constraint packer, not a full MIP solver.
