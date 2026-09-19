# MM-045 — Web, macOS, Windows, iPhone, and Android applications — implementer evidence

Item: MM-045
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [app.web, app.macos, app.windows, app.ios, app.android]`
- `src/movie_muse/platforms/**`
- `apps/web/**`, `apps/macos/**`, `apps/windows/**`, `apps/ios/**`, `apps/android/**`
- `tests/platforms/**`, `tests/apps/**`
- `frontend/src/platforms/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Five live hosts open the same golden project, document, revision, and layout
hash. Web/macOS/Windows keep professional long-form authoring. iPhone/Android
emphasize Room, consent-first capture, cards, approvals, references, and
fast annotations under a 2s / 44pt accessibility budget, with explicit
long-form limitations. Offline edits recover after close. Auth/subscription
outages keep local work and fail-close sync upload. Storage uses
origin-isolated OPFS (web), Application Support 0700 (macOS), LocalAppData
(windows), NSFileProtectionComplete (iOS), and MODE_PRIVATE (Android).

## Commands

See `quality-commands.txt`. Headline: 20 focused tests passed; full pytest
1042 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T09:00:00Z`
SHA: `ce67f4e091ffaa055a58dd153ed3fa039f10841f`
fingerprint: `6f4e6367cb85719d75b85dd7393868fc2cc6966df9e29a60e48c15c144ff66ab`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Hosts are Python application runtimes plus a web shell; they are not
  App Store / Play packaged binaries.
- Frontend vitest was not run here because `frontend/node_modules` is absent.
