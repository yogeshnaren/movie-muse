# MM-022 — Creative Divergence / writer-unblock — implementer evidence

Item: MM-022
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.writer_unblock]`
- `src/movie_muse/writer_unblock/**`
- `tests/writer_unblock/**`

Did not add `fixtures/**` (would STALE MM-012). Did not mark PASS.

## What was built

`WriterUnblockService` emits eight structurally distinct divergence
routes as pending proposals on non-canonical branches. Divergence
uses ModelRouter `propose_alternatives` with the divergence role.
Prose requires explicit Executor mode (`generate_text` + executor).
Writers can combine, edit, or reject candidates. Suggestion metrics
require consent and set `training_eligible=False`. Hidden-authority
language is rejected.

## Commands

See `quality-commands.txt`. Headline: 7 writer_unblock tests passed;
full pytest 645 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T20:58:08Z`

## Known limitations

- Route candidate text is catalog-driven; ModelRouter doubles supply
  provenance, not live creative copy.
- Usefulness feedback is stored and never training-eligible.
- `verify_all.sh` remains fail-closed until later named gates exist.
