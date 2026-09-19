# MM-047 — Golden-path E2E, independent verification, and release gate — implementer evidence

Item: MM-047
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [test.golden_path, script.verify_all]`
- `tests/golden_path/**`, `fixtures/golden_path/**`
- `scripts/verify_all.sh`, `scripts/gates/**`

Did not add new `fixtures/**` files. Did not self-PASS. Did not mock required
live EXT gates. Did not edit `scripts/verify_all.sh` (dual-owned with MM-001).
Edited `tests/release/test_verify_all_fail_closed.py` (MM-001 owned) so adding
named gates does not break fail-closed pytest; did not `invalidate --apply`.

## What was built

Every named `verify_all.sh` gate is an executable `scripts/gates/<name>.sh`.
Shared `_run_pytest.sh` runs focused suites. `external_live_providers.sh` runs
fail-closed contract tests then exits 1 with `missing_live_gates=` when any
`required_for_final` EXT status is not PASS.

`tests/golden_path` boots one project from `golden_project_and_document()` and
walks the 41-step journey over public `*.api` surfaces only (no `from tests.*`).
Step 41 opens all five platforms with the same `GOLDEN_PROJECT_ID` /
`GOLDEN_DOCUMENT_ID` / layout hash. Live `require_*` helpers fail closed.

## Commands

See `quality-commands.txt`. Headline: 5 focused golden-path tests passed;
full pytest 1077 passed; ruff `--no-cache` / mypy clean; `verify_all.sh` exits 1
at `external_live_providers` with all eight required EXT ids listed. Product
sentinel is not printed.

UTC: `2026-09-19T12:30:00Z`
SHA: `9f849f7a5366fc9f89af6f7680f8d7e190a2e1b6`
fingerprint: `292d0901c1689000622372c3bd79f8fd1493d7f34228e9cd9344988ca4686637`

## Known limitations

- Required live/sandbox gates remain `NOT_RUN` in this environment:
  EXT-FDX-FINAL-DRAFT, EXT-REMOTE-MODEL, EXT-ZOOM-SANDBOX,
  EXT-GOOGLE-MEET-SANDBOX, EXT-IMAGE-PROVIDER, EXT-VIDEO-PROVIDER,
  EXT-DELIVERY-CHANNEL, EXT-INSURANCE-PARTNER.
- MM-047 acceptance (`./scripts/verify_all.sh` prints the product PASS
  sentinel) cannot be met until those gates have genuine sandbox evidence.
- Harbor `load_golden_path_project` is a separate airplane seed; cross-platform
  identity uses the platform golden IDs.
