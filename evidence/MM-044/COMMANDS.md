# MM-044 — Public API, webhooks, MCP, and interoperability — implementer evidence

Item: MM-044
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.api, module.mcp, module.webhooks]`
- `src/movie_muse/api/**`
- `src/movie_muse/mcp/**`
- `src/movie_muse/webhooks/**`
- `backend/app/**`
- `tests/api/**`
- `tests/mcp/**`
- `tests/webhooks/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.
Did not add a new EXT gate.

## What was built

Versioned least-privilege Integration Mesh for projects, revisions, proposals,
approved artifacts, and status. MCP tools declare `ToolSide` READ / PROPOSE /
COMMIT. Integrations may propose; only humans commit. Signed HMAC webhooks
with replay protection record `network_sent=False`. Adapter SDK includes a
fail-closed specialist production/review connector
(`MOVIE_MUSE_REVIEW_CONNECTOR_BASE_URL`) plus open-file fallback through
approved `ArtifactService.export_version`. Capability registry, sync ledger,
token vault, per-field source-of-truth, OpenAPI, prompt-injection rejection,
idempotency, rate limits, and backward-compatibility (`v1` only) are tested.

FastAPI host in `backend/app` imports `movie_muse.api.api` and
`movie_muse.webhooks.api` only. SQLite `LocalStore` is not bound to
Starlette TestClient portal threads.

## Commands

See `quality-commands.txt`. Headline: 27 focused tests passed; full pytest
1022 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T08:10:00Z`
SHA: `03ea91bc260c2c0c56ed066bfb4143fddbdd6542`
fingerprint: `d1c86af9829f2c933b8fab5fc98b9e0d844e98cd32463dbc95ae83ac46d8ba4e`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Live specialist connector stays fail-closed without
  `MOVIE_MUSE_REVIEW_CONNECTOR_BASE_URL`; mocks do not satisfy a live gate.
- HTTP TestClient coverage is `/health` 200 and unbound `/v1/status` 503
  because SQLite connections are not cross-thread safe.
