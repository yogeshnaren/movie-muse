# MM-038 — Budget Evidence Ledger — implementer evidence

Item: MM-038
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.budget]`
- `src/movie_muse/budget/**`
- `tests/budget/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`BudgetService` compiles a chart-of-accounts ledger from a current schedule.
Schedule-derived shooting days, company moves, and cast quantities use
qty×rate×fringe formulas rounded half-even. Contingency is formula-backed;
incentives and overrides are explicit estimates with source/date/territory/
currency evidence. Totals reconcile to the sum of rounded lines. Maturity
calibration reports coverage/error/bias by maturity, department, geography,
and budget class. “Extremely accurate” claims fail closed unless residuals
are validated at bid-backed or forecast-to-complete maturity. Schedule
changes stale the ledger.

## Commands

See `quality-commands.txt`. Headline: 20 focused tests passed; full pytest
812 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T01:22:48Z`
SHA: `2eddd6ec9b3b747b0e74b42b74e14c28bdc4bd85`
fingerprint: `398fdf8ddd2614c6feedb9fae6dea308df2bbaa50e4acdc7ffdccd1ec8a83260`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- USD cents only; mixed currencies fail closed.
