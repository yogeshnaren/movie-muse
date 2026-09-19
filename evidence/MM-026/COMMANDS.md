# MM-026 — Single/multi-writer Room Mode — implementer evidence

Item: MM-026
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.room_mode]`
- `src/movie_muse/room_mode/**`
- `tests/room_mode/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`RoomModeService` starts solo or multi-writer rooms in writer or research-team
mode. Simulated seats are labeled simulated and cannot be presented as humans.
A solo room refuses a second human writer. Capture goes through
`ProjectMemoryService` and never auto-promotes. Room Harvest requires
`start_harvest_review` before promote/discard. Timers, boards, votes,
acknowledgements, and proposal attachments are session-durable. Attribution
follows the capturing principal's actor id and ACL.

## Commands

See `quality-commands.txt`. Headline: 11 focused tests passed; full pytest
707 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T22:44:43Z`
SHA: `71640a70962cf3d06b83240bde47a2b15a88633d`
fingerprint: `4ad07c818a7a97978abfc51af293a1c84315b59e57327baeae52b8924419a4dc`

## Known limitations

- Idea candidates remain unpromotable to sealed `ProjectMemoryKind` (MM-002);
  harvest of ideas is discard/review, not schema ProjectMemory promotion.
- Conflict/proposal voting stores ballot records; it does not call
  `ProposalService.accept`.
- `verify_all.sh` remains fail-closed until later named gates exist.
