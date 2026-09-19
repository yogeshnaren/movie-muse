# MM-025 — Project Memory and reviewed capture — implementer evidence

Item: MM-025
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.project_memory]`
- `src/movie_muse/project_memory/**`
- `tests/project_memory/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`ProjectMemoryService` captures typed candidates (idea, decision, question,
research, assignment, rejected idea, fact, link) with branch/revision scope
and provenance. Candidates never become schema `ProjectMemory` automatically.
Humans promote decision/fact/assignment/research into `ProjectMemory`.
Rejected ideas remain retrievable and never enter `list_memories`. Edits
append provenance. Duplicate same-kind/summary/branch candidates fail closed
unless explicitly superseded.

## Commands

See `quality-commands.txt`. Headline: 11 focused tests passed; full pytest
682 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T22:01:48Z`
SHA: `979b83e4361b4f5362b85800365b723a84af4948`
fingerprint: `3bffb56c02c951d8b74591acb1b2d962329bdcfe12f32791b4be243bd6a77365`

## Known limitations

- Idea, question, and link candidates are first-class but not mappable to
  the sealed `ProjectMemoryKind` enum (MM-002 schema); they stay reviewed
  candidates rather than schema ProjectMemory rows.
- `verify_all.sh` remains fail-closed until later named gates exist.
