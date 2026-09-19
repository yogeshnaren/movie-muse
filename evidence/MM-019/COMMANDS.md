# MM-019 — Character knowledge and deterministic state engine — implementer evidence

Item: MM-019
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.state_engine]`
- `src/movie_muse/state_engine/**` deterministic reducer over FilmIR scene order
- `tests/state_engine/**`

Did not add `fixtures/**` (would STALE MM-012). Did not call ModelRouter
from the reducer. Did not invent ProjectMemory or CreativeIntentIR
services. Did not mark PASS.

## What was built

`StateEngine.reduce` extracts structural location/world transitions from
FilmIR, wraps inferred claims as lowest-authority candidates, merges
persisted human corrections, and reduces interval facts by scene.

Temporal queries are deterministic. Same-scene or polarity conflicts
record a `Contradiction` with evidence ids. Later-scene value changes
(for example kitchen → harbor) are succession, not contradictions.
`StateEngine.correct` requires ACCEPT, forces `EpistemicLevel.AUTHORED`,
and persists through `workspace_meta` / blobs. Declared corpus
thresholds are all 1.0.

## Commands

See `quality-commands.txt`. Headline: 9 state_engine tests passed;
full pytest 616 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-06T00:32:00Z`

## Known limitations

- Candidate extraction beyond FilmIR location/world is supplied as
  inferred claims or extra transitions; the reducer never calls a model.
- Fixture FilmIR goldens remain deferred.
- `verify_all.sh` remains fail-closed until later named gates exist.
