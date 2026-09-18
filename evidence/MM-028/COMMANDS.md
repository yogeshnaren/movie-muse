# MM-028 — Meeting capture and transcript intelligence — implementer evidence

Item: MM-028
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.meeting_capture]`
- `src/movie_muse/meeting_capture/**`
- `tests/meeting_capture/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`MeetingCaptureService` is consent-first. Consent and capture state are
visible. Recording and import fail closed without granted consent, and after
deny/withdraw. Transcripts are stored as restricted generic artifacts.
Speaker corrections and text edits keep provenance and mint a new artifact
version. Media links and utterances are searchable. Extracted candidates
never auto-promote; Room Harvest requires explicit review. Deletion clears
transcript payload; retention expiry fail-closes reads.

## Commands

See `quality-commands.txt`. Headline: 11 focused tests passed; full pytest
718 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T23:03:24Z`
SHA: `6e598fe4bae0f46dd30ac52a35fdc1dce5de3754`
fingerprint: `73f78aecdfe07ca864ba5794bc99824ad00cac32fcf0ea8a1bf264fab14ddb5b`

## Known limitations

- Meeting harvest wraps `ProjectMemoryService`; it does not dual-write into
  a live `RoomModeService` session unless a `room_id` is stored as metadata.
- Provider adapters (Zoom/Meet) are MM-029.
- `verify_all.sh` remains fail-closed until later named gates exist.
