# MM-020 — CreativeIntentIR and creator invariants — implementer evidence

Item: MM-020
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.creative_intent]`
- `src/movie_muse/creative_intent/**` versioned creator-owned intent
- `tests/creative_intent/**`

Did not add `fixtures/**` (would STALE MM-012). Did not call ModelRouter.
Did not edit schema internals. Did not mark PASS.

## What was built

`CreativeIntentService` persists versioned `CreativeIntentIR` envelopes.
Direct manipulation and chat write the same typed `IntentCommand`
(`canonical_payload` is origin-independent). Inferred suggestions cannot
be locked and cannot become stated except through explicit
`accept_suggestion` (new id; historic inferred record stays inferred).
Stale revision applies fail closed. Branch fork/merge copies or
conflicts. Scene scope can validate against FilmIR scene order.

## Commands

See `quality-commands.txt`. Headline: 11 creative_intent tests passed;
full pytest 627 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T20:10:00Z`

## Known limitations

- Suggestion text is supplied by the host; this package does not invoke a model.
- Fixture FilmIR goldens remain deferred.
- `verify_all.sh` remains fail-closed until later named gates exist.
