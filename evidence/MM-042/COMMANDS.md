# MM-042 — Commercial scenario forecasting — implementer evidence

Item: MM-042
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.commercial_forecast]`
- `src/movie_muse/commercial_forecast/**`
- `tests/commercial_forecast/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Comparables-backed P10/P50/P90 commercial scenarios. Every number traces to
data dates, method, assumptions, and selected titles. Time-split backtests
reject leakage. Poor coverage and out-of-distribution territory/platform
fail closed to insufficient evidence. Outputs are ranges, not a single
guaranteed number.

## Commands

See `quality-commands.txt`. Headline: 20 focused tests passed; full pytest
973 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T05:15:00Z`
SHA: `4cb2670009732704060641d7ecb06d04197fb7dd`
fingerprint: `a4150b363bf8d3497abbb0942400630a47b605ad8bfe76d75cacb9e0e6aaac66`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Deterministic comparable ratios are not live box-office feeds.
