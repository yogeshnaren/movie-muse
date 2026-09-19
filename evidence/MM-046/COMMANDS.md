# MM-046 — Security, privacy, observability, evaluation, and operations — implementer evidence

Item: MM-046
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [global.security, global.privacy, global.observability, global.evaluation, global.operations]`
- `src/movie_muse/security/**`, `tests/control_plane/**`, `docs/security/**`
- `src/movie_muse/privacy/**`, `tests/privacy/**`, `docs/privacy/**`
- `src/movie_muse/observability/**`, `tests/observability/**`
- `src/movie_muse/evaluation/**`, `tests/evaluation/**`, `bench/**`
- `src/movie_muse/operations/**`, `tests/operations/**`, `docs/operations/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`,
`pyproject.toml`, `tests/toolchain/**`, `tests/release/**`, `scripts/gates/**`,
or `scripts/verify_all.sh`. Security tests live under `tests/control_plane/**`
so `tests/security/**` remains toolchain-owned.

## What was built

`ControlPlane` boots identity, ACL, and the five MM-046 services. HIGH/CRITICAL
findings block ready. Classification remote max is internal. Secrets use stdlib
SHA-256 counter-mode plus HMAC; BYOK fails closed without a customer key.
Privacy keeps no-training default and no cross-user prompt cache; erasure and
export are fail-closed. Telemetry redacts prompt/secret keys. Evaluation loads
`fixtures/bench/tasks.yaml` and requires local/fine-tuned routes to meet quality
and safety baselines. Operations emit an SBOM, enforce cost caps, and require
an independently reproduced backup/restore drill before incident close.

## Commands

See `quality-commands.txt`. Headline: 30 focused tests passed; full pytest
1072 passed; ruff `--no-cache` / mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T10:20:00Z`
SHA: `661b3dbbd5707352d7461b5404704e0f366ea5e7`
fingerprint: `03fe8b9f6c03db672becde7e6fde7d8a5e39c2655b1a467e568fd2ea4320e917`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Fine-tuned evaluation uses the in-repo `finetune_script_adapter` /
  `ft-script-v1` stub, not a live training job.
- Backup/restore drill is local sqlite plus blobs, not an offsite replica.
