# MM-024 — Continuity and material production-impact analysis — implementer evidence

Item: MM-024
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.continuity, capability.impact]`
- `src/movie_muse/continuity/**`
- `tests/continuity/**`
- `src/movie_muse/impact/**`
- `tests/impact/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`ContinuityService.analyze` reduces FilmIR through `StateEngine` and maps
contradictions (and misunderstandings) onto evidence-bearing findings with
HIGH/MEDIUM/LOW materiality. Author mode compresses LOCATION/WORLD/WARDROBE
logistics; production mode may invert that emphasis. Humans can resolve or
suppress findings with audit; integrations cannot close findings. Users can
inspect all known consequences, including compressed logistics.

`ImpactService.summarize` projects visible findings into `ImpactSummary`
(semantic / continuity / production). Optional `DependencyEngine` labels
stale derived nodes as production consequences when present.

High-severity in-test defects (same-scene POSSESSION/KNOWLEDGE/SECRET
conflicts) are recalled at the declared 1.0 threshold. False-positive budget
is measured on a clean temporal-succession corpus.

## Commands

See `quality-commands.txt`. Headline: 19 focused tests passed; full pytest
671 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T21:45:29Z`
SHA: `0f533e4ec9398e96a635cd86c961e25badec836a`
fingerprint: `0dd9acc56a54b7d4b65eb5e6615ea64f83992473b151b0e5a5911db59f88dace`

## Known limitations

- Similarity of impact lines is deterministic string projection, not a model.
- Dependency-graph stale labels are included only when a DependencyEngine is
  injected; MM-011 is not a DAG dependency of MM-024.
- `verify_all.sh` remains fail-closed until later named gates exist.
