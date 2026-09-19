# MM-017 — Context builder and rights-controlled retrieval — implementer evidence

Item: MM-017
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.context, module.retrieval]`
- `src/movie_muse/context/**` token/model-independent assembly
- `src/movie_muse/retrieval/**` rights-controlled retrieval
- `tests/context/**` and `tests/retrieval/**`

Did not add `fixtures/**` (would STALE MM-012). Did not implement
ProjectMemory/CreativeIntentIR/FilmIR/state services (later packages).
Those types are optional schema inputs. Did not call ModelRouter from
assembly. Did not mark PASS.

## What was built

`ContextService.assemble` builds citation-bearing segments from the live
revision, optional ProjectMemory, CreativeIntentIR, bound typed states,
and permitted retrieval hits. Tenant/branch mixing and stale canon fail
closed. Budget is chars/bytes/segment count.

`RetrievalService` indexes and retrieves only sources that pass
`RightsService.require_permitted_use` for RETRIEVAL and CITATION.
Unlicensed/disallowed sources fail closed. Instruction-like retrieved
text is redacted or rejected. Retrieved text is data, never instructions.

## Commands

See `quality-commands.txt`. Headline: 32 context/retrieval tests passed;
full pytest 591 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-06T00:20:00Z`

## Known limitations

- ProjectMemory and CreativeIntentIR services are not built (MM-025 / MM-020).
- FilmIR compiler and state engine are not built (MM-018 / MM-019).
- Local/remote model invoke remains unset/fail-closed; assembly does not
  route through ModelRouter.
- `verify_all.sh` remains fail-closed until later named gates exist.
- EXT-FDX-FINAL-DRAFT and EXT-REMOTE-MODEL remain NOT_RUN.
