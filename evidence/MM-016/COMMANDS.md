# MM-016 — Competitive workflow regression suite — implementer evidence

Item: MM-016
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [test.competitive]`
- `docs/competitive/**` dated workflow matrix and protocol
- `tests/competitive/**` release-blocking automation for `supported` rows

Did not add `fixtures/**` (would STALE MM-012). Did not claim product
equivalence. Did not implement MM-017 or later. Did not mark PASS.

## What was built

A non-infringing matrix against professional expectations represented by
Final Draft, Celtx, Arc Studio, Filmustage, and Scriptation.

Results are `supported`, `gap`, or `external`. `supported` rows have
automated tests. `gap` rows name the awaiting package. `external` names
`EXT-FDX-FINAL-DRAFT` and stays fail-closed without a licensed binary.

## Commands

See `quality-commands.txt`. Headline: 13 competitive tests passed; full
pytest 559 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-05T23:50:00Z`

## Known limitations

- Licensed Final Draft inspection is `external` / `NOT_RUN`.
- Breakdown, schedule, budget, live collab, PDF ingest, and annotation
  transfer are documented gaps.
- `verify_all.sh` remains fail-closed until later named gates exist.
