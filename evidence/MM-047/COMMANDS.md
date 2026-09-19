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

## Independent verification (Grok 4.6)

Verifier `movie-muse-independent-verifier/grok-4.6/2026-09-19T07:35:00Z`
verified a detached worktree at
`7e7b69de7c46e7f5c3e8fb309ffcc138e7b184d8`
(fingerprint `26f4404c3ace288dc93e642f7a712acfb34c95afaa252254dabc8fdc2fbedef0`).
Implementation quality (validate, ruff, mypy, golden_path, full pytest,
probes A–K) was green. Product-acceptance result is FAIL because
`./scripts/verify_all.sh` cannot print the PASS sentinel without live EXT
gates. Ledger stamped `BLOCKED_EXTERNAL`, not PASS and not FAIL.

UTC: `2026-09-19T13:00:00Z`

## Independent verification (Grok 4.6) — dual-mode golden path

Verifier `movie-muse-independent-verifier/grok-4.6/2026-09-19T08:17:40Z`
verified a detached worktree at
`6f977a9ef1061bf6ae5a5bbbfb55170e44628b16`
(fingerprint `baf3cbb8f13d3af30cc35435582c64b75e7031784147944b40ea802feca2e5de`).
Implementation quality PASS (validate, ruff, mypy, 6 golden_path, 1078 full
pytest, probes A–K). Product-acceptance FAIL because
`./scripts/verify_all.sh` cannot print the PASS sentinel without live EXT
gates. Ledger stamped `BLOCKED_EXTERNAL`, not PASS.

UTC: `2026-09-19T15:00:00Z`

## Independent verification (Grok 4.6) — live probes

Verifier `movie-muse-independent-verifier/grok-4.6/2026-09-19T08:46:38Z`
verified a detached worktree at
`a1cb3fd0fc309018b45a5bf117ac8dacbfc7d3b6`
(fingerprint `4f40ab309aff0c4b884e7ee2b6ac357652959cc8f6cb73e7cf22e6599a50ed1a`).
Implementation quality PASS (8 golden_path, 1080 full pytest, fail-closed
live probes A–H). Product-acceptance FAIL because live/sandbox providers are
unset. Dummy unreachable URLs also fail closed. Ledger stamped
`BLOCKED_EXTERNAL`, not PASS.

UTC: `2026-09-19T16:45:00Z`

## Continuation (2026-09-19T14:00:00Z)

Golden path no longer forbids an all-EXT-PASS world. Live `require_*` calls
are dual-mode. Steps 29/31/34 now run local previs review, correspondence
send, and insurance handoff. Product PASS is still blocked on genuine live
EXT evidence; this revision is not a self-PASS.

## Continuation (2026-09-19T17:00:00Z)

`scripts/gates/golden_path_41_steps.sh` now runs `_completion_preflight.py`
after golden-path pytest. The preflight fails closed on a dirty worktree,
unsupported Python, drifted PASS fingerprints, or missing evidence files.
It does not print the product sentinel. Live EXT remains the required
external blocker; fingerprint drift on MM-001/MM-004/MM-015 is recorded but
not `invalidate --apply`. This revision is not a self-PASS.

## Independent verification (Grok 4.6) — completion preflight

Verifier `movie-muse-independent-verifier/grok-4.6/2026-09-19T09:20:19Z`
verified a detached worktree at
`d9a025b22ca195d99be774a87e065bcbf8b00e41`
(fingerprint `ac8d2cab71e4810207d1d99fe9ed9fa91317908170418ab07d04204c4e3b8a52`).
Implementation quality PASS (9 golden_path, 1081 full pytest, probes A–K).
Product-acceptance FAIL because live/sandbox providers are unset. Dummy
unreachable URLs also fail closed. Completion preflight reports drifted
fingerprints for MM-001/MM-004/MM-015. Ledger stamped `BLOCKED_EXTERNAL`,
not PASS.

UTC: `2026-09-19T20:00:00Z`

## Independent verification (Grok 4.6) — fingerprint restore

Verifier `movie-muse-independent-verifier/grok-4.6/2026-09-19T10:03:09Z`
verified a detached worktree at
`d4ca41ec21334f95dae1e7ce576ac8fea9b27d79`
(fingerprint `e80c0c239eb93cc334f54f4be44932281ada043b39faa0d1301de7734d14e85a`).
Implementation quality PASS (41 focused, 1081 full pytest, probes A–J).
MM-015 and MM-027 fingerprints match recorded PASS. Product-acceptance FAIL
because live/sandbox providers are unset. Completion preflight reports
MM-001/MM-004/MM-045 drift. Ledger stamped `BLOCKED_EXTERNAL`, not PASS.

UTC: `2026-09-19T20:00:00Z`

## Known limitations

- Required live/sandbox gates remain `NOT_RUN` in this environment:
  EXT-FDX-FINAL-DRAFT, EXT-REMOTE-MODEL, EXT-ZOOM-SANDBOX,
  EXT-GOOGLE-MEET-SANDBOX, EXT-IMAGE-PROVIDER, EXT-VIDEO-PROVIDER,
  EXT-DELIVERY-CHANNEL, EXT-INSURANCE-PARTNER.
- MM-047 acceptance (`./scripts/verify_all.sh` prints the product PASS
  sentinel) cannot be met until those gates have genuine sandbox evidence.
- Harbor `load_golden_path_project` is a separate airplane seed; cross-platform
  identity uses the platform golden IDs.
