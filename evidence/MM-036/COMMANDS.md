# MM-036 — Department handoffs and production correspondence — implementer evidence

Item: MM-036
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.department_handoff, capability.correspondence]`
- `src/movie_muse/department_handoff/**`
- `tests/department_handoff/**`
- `src/movie_muse/correspondence/**`
- `tests/correspondence/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`DepartmentHandoffService` exposes role-filtered department packets over a
derived breakdown. Craft-owner confirm/correct/add-assumption/ask-director/N-A
emit existing ProjectEvent types (`DepartmentDecisionConfirmed`,
`AssumptionChanged`, `ProductionRequirementConfirmed`) into canonical
operational state. Screenplay-change notices are department-targeted and
acknowledgeable. Assignments require a cross-department role. Exports require
`EXPORT`. Departments see permitted data only.

`CorrespondenceService` drafts restricted generic-artifact messages, previews
recipients and content, requires human approve, and records local delivery
only after explicit `confirm=True`. Live network send is not enabled.
`EXT-DELIVERY-CHANNEL` remains NOT_RUN; mocks do not satisfy that live gate.

## Commands

See `quality-commands.txt`. Headline: 18 focused tests passed; full pytest
779 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T00:38:48Z`
SHA: `48ac23edbe194bf02423442c05df7088b9b1e874`
fingerprint: `867b98c23af8d6f26be19d656832a433a8969759b621e98276d7102e009e60d2`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- `EXT-DELIVERY-CHANNEL` stays NOT_RUN. Contract tests prove fail-closed
  local delivery records (`network_sent=False`); they do not claim live
  channel integration.
