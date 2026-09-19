# MM-009 — Model router, provider adapters, local models, and policy — implementer evidence

Item: MM-009
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-009.pass_record.

## Scope

`scope_keys: [module.model_router, policy.models]`
- `src/movie_muse/model_router/**` public `movie_muse.model_router.api`
- `policy/models/**` capabilities, providers, consent, classification, budgets, cache, role contracts
- `tests/model_router/**`, `tests/policy/models/**`

Did not edit MM-001 through MM-008 owned files, `pyproject.toml`, persistence
SQLite migrations, schemas, ChangeSet ops, EVENT_TYPES, or `tests/__init__.py`.
Did not implement MM-010 or later. Did not mark EXT-REMOTE-MODEL PASS.

## What was built

1. **ModelRouter.** `route()`, `quote()`, and `execute()` over policy. Requests
   declare capability, classification, latency/cost budget, offline, context
   size, structured output, quality tier, role contract, and ACL snapshot.
   Decisions record provider, model, reason, policy version, capability,
   classification, offline, and cost quote id. No chain-of-thought field.
2. **Policy.** YAML under `policy/models/` chooses double vs local vs remote,
   enforces consent, classification ranks, budgets, cache keys, and epistemic
   role contracts. Actor/audience cannot calculate production numbers.
3. **Adapters.** DeterministicDoubleAdapter (no network), LocalModelAdapter
   (in-process stub; unset `MOVIE_MUSE_LOCAL_MODEL_RUNTIME` fails honestly),
   RemoteProviderAdapter (stdlib HTTP; unset `MOVIE_MUSE_REMOTE_MODEL_BASE_URL`
   raises `ProviderUnavailableError`), FineTunedAdapter (adapter id + base route).
4. **Storage.** Content-addressed blobs + `model_router.index_digest`. No new
   SQLite tables. Quotes, decisions, usage, prompt versions, cache.
5. **Paid ops.** Preflight `quote()` then `execute()` requires
   `Action.RUN_PAID_PROVIDER`. Viewers are denied. Owner can authorize.
6. **AI-off / offline.** Project.ai_off and disabled capabilities fail closed.
   RevisionService still saves. Airplane/offline denies remote; doubles remain.
7. **Smoke.** `tests/model_router/test_remote_smoke.py` never uses pytest.skip.
   Unset env asserts ProviderUnavailableError. Live round-trip only if env set.
   EXT-REMOTE-MODEL stays NOT_RUN.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`35b79c09389016c2a7449b643e21aa534915446a`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: no issues found in 120 source files |
| `PYTHONPATH=src python3 -m pytest tests/model_router tests/policy/models -q` | 35 passed |
| `PYTHONPATH=src python3 -m pytest tests/model_router tests/policy/models tests/jobs tests/worker tests/authorization -q` | 81 passed |
| `PYTHONPATH=src python3 -m pytest` | 393 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-009`, `MM-010`, `MM-011` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-009` | `a3eda7bba96e49d334887e9eb471d51d42c3b407048fd2f3552612534a8ccc20` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `35b79c09389016c2a7449b643e21aa534915446a`
Prior implementation commit: `94da62290f41c6aee46be8e81f8d2c1dd226fe6e`
Input fingerprint at `35b79c0`: `a3eda7bba96e49d334887e9eb471d51d42c3b407048fd2f3552612534a8ccc20`
UTC: `2026-09-01T16:09:26Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-009` at
the evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- Local adapter is an in-process stub gated by `MOVIE_MUSE_LOCAL_MODEL_RUNTIME`;
  it does not load a real GGUF/ONNX runtime.
- Remote adapter is generic HTTP `POST {base}/invoke`, not a vendor SDK.
- `MOVIE_MUSE_REMOTE_MODEL_BASE_URL` was unset in this environment, so the live
  smoke asserted `ProviderUnavailableError` (fail-closed). EXT-REMOTE-MODEL
  remains NOT_RUN. Do not treat that as a live PASS.
- `verify_all.sh` remains fail-closed until later packages add named gates.

## Required external gates

- EXT-REMOTE-MODEL (owner MM-009): **NOT_RUN**. Required for final. Must be a
  real configured provider round-trip; mocks cannot satisfy the live gate.

## Verifier instructions

1. Fresh detached checkout of `35b79c09389016c2a7449b643e21aa534915446a` or
   this evidence commit. Recompute fingerprint MM-009 at that HEAD. At
   `35b79c0` it must be
   `a3eda7bba96e49d334887e9eb471d51d42c3b407048fd2f3552612534a8ccc20`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-008 are current PASS and MM-009 is IN_PROGRESS
   with `pass_record: null`. Confirm EXT-REMOTE-MODEL is NOT_RUN.
3. Run ruff, mypy src, focused pytest (`tests/model_router tests/policy/models`),
   affected (`tests/jobs tests/worker tests/authorization`), and full pytest.
4. Probes:
   - Project `ai_off=True`: `route()` raises `AiOffError`; `RevisionService.apply_change_set` still saves.
   - Capability `disabled_capability` denies generation.
   - Viewer cannot `execute()` a paid remote route (`Action.RUN_PAID_PROVIDER` denied); owner can quote then execute.
   - Unset `MOVIE_MUSE_REMOTE_MODEL_BASE_URL`: `RemoteProviderAdapter.invoke` raises `ProviderUnavailableError`; the smoke test must not `pytest.skip`.
   - Role contract: actor/audience + `calculate_production` denied; `production_analyst` allowed.
   - Identical accepted execute is a cache hit; provenance has provider, model version, prompt version, policy version, timestamp; no `chain_of_thought`.
   - Fallback from unavailable remote uses only classification-allowed providers; restricted data cannot fall back to remote.
   - Prompt id+version is immutable; fine-tuned adapter is a route (`provider_kind=fine_tuned`).
   - model_router imports only `*.api` siblings (plus allowed toolchain); jobs/worker/document/revisions do not import provider SDKs.
   - No new SQLite tables; index lives at `model_router.index_digest`.
5. Do not treat this implementer record as PASS. Do not mark EXT-REMOTE-MODEL PASS when the remote env is unset.
