# MM-027 — Live collaboration and sync — implementer evidence

Item: MM-027
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.collaboration, module.sync]`
- `src/movie_muse/collaboration/**`
- `tests/collaboration/**`
- `src/movie_muse/sync/**`
- `tests/sync/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`CollaborationService` provides ephemeral presence (TTL 30s), durable comments
and decisions, CRDT merge for collab ops, conflict UI for concurrent same-
target document patches (no last-writer-wins, no silent loss), and fail-closed
stale/unauthorized/forbidden-domain operations. A CRDT may coordinate authored
document/comments/cursors/presence; it cannot mutate FilmIR, intent, production,
budget, financial, or scenario state. `SyncProtocol.reconnect()` resumes after
outage while preserving `drain_inbox`. Decisions are captured as
`CollaborationEvent` and never auto-promoted.

## Commands

See `quality-commands.txt`. Headline: 25 focused collaboration+sync tests
passed; full pytest 696 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T22:20:36Z`
SHA: `97542c6d009f172ec1329a558c81daff7fec71ca`
fingerprint: `162b267f1f6d81351960a5896f828ea5f09d2fd4cc520d16ce7a9ae31ebeb7fe`

## Known limitations

- Presence is in-memory / workspace-meta indexed with a 30s TTL; it is not a
  durable CollaborationEvent.
- Concurrent same-target patches surface `ConflictView` and withhold both
  conflicting patches from apply-order until resolved; they are not auto-merged.
- `verify_all.sh` remains fail-closed until later named gates exist.
