# MM-018 — Screenplay compiler and FilmIR extraction — implementer evidence

Item: MM-018
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.compiler, module.film_ir]`
- `src/movie_muse/compiler/**` deterministic syntax compiler
- `src/movie_muse/film_ir/**` versioned FilmIR + ModelRouter extraction
- `tests/compiler/**` and `tests/film_ir/**`

Did not add `fixtures/**` (would STALE MM-012). Fixture FilmIR goldens
remain deferred. Did not promote inferred claims to AuthoredFact or
FilmIR entities. Did not mark PASS.

## What was built

`CompilerService.compile` derives scenes, characters, locations, and
props from the document kernel with no model call.

`FilmIrService.project` writes a content-addressed FilmIR from that
compile (idempotent on revision). `extract_candidates` is the only AI
path and must go through `ModelRouter.quote` / `execute`. Invalid
structured output repairs once or fails closed. Precision/recall is
scored against compiler ground truth.

## Commands

See `quality-commands.txt`. Headline: 16 compiler/film_ir tests passed;
full pytest 607 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-06T00:50:00Z`

## Known limitations

- Fixture `expected/film_ir.json` goldens stay deferred (updating them
  would STALE MM-012).
- Local/remote model invoke remains unset/fail-closed; tests use the
  deterministic double route.
- `verify_all.sh` remains fail-closed until later named gates exist.
