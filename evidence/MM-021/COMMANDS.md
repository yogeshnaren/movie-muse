# MM-021 — Proposal/ChangeSet and impact review engine — implementer evidence

Item: MM-021
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.proposals]`
- `src/movie_muse/proposals/**` inspectable proposals and impact review
- `tests/proposals/**`

Did not add `fixtures/**` (would STALE MM-012). Did not call ModelRouter.
Did not edit schema internals. Did not mark PASS.

## What was built

`ProposalService` is the permissioned facade over stored ChangeSet
proposals. AI/integration principals may submit inspectable proposals
(with impact, alternatives, and evidence ids) but cannot accept canon
(`DirectCanonWriteError`). Partial acceptance names operation ids and
leaves an explicit remainder. Stale proposals fail closed until rebase.
Accepted proposals create a revision, an audit event, and dependency
graph invalidations.

## Commands

See `quality-commands.txt`. Headline: 11 proposals tests passed;
full pytest 638 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T20:38:00Z`

## Known limitations

- Impact summaries are supplied by the host; this package does not invoke a model.
- Fixture FilmIR goldens remain deferred.
- `verify_all.sh` remains fail-closed until later named gates exist.
