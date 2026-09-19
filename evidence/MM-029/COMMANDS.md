# MM-029 — Zoom and Google Meet adapters — implementer evidence

Item: MM-029
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [adapter.zoom, adapter.google_meet]`
- `src/movie_muse/adapters/zoom/**`
- `src/movie_muse/adapters/google_meet/**`
- `tests/adapters/zoom/**`
- `tests/adapters/google_meet/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

Replaceable Zoom and Google Meet OAuth/webhook/import adapters with declared
least scopes, HMAC signed callback validation, replay protection, and
consent-first import through `MeetingCaptureService`. Expired and revoked
credentials fail closed. Live `exchange_authorization_code` and
`import_live_recording` require sandbox env vars and do not treat contract
tests as live evidence. `EXT-ZOOM-SANDBOX` and `EXT-GOOGLE-MEET-SANDBOX`
stay NOT_RUN.

## Commands

See `quality-commands.txt`. Headline: 21 focused tests passed; full pytest
848 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T02:06:48Z`
SHA: `ae3e1f54bfd99647de5af974c856c40ec6481c49`
fingerprint: `9155b2ae7a326f4a4a969a2a45584b187ee049d6d0687c1b8f34718ffa68b9c8`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Live Zoom/Meet sandbox OAuth is not claimed; mocks do not satisfy the
  required live gates.
