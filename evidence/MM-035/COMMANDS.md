# MM-035 — Production breakdown — implementer evidence

Item: MM-035
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.breakdown]`
- `src/movie_muse/breakdown/**`
- `tests/breakdown/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`BreakdownService` derives cast, extras, locations, props, wardrobe, makeup,
vehicles, animals, stunts, intimacy, minors, VFX/SFX, sound, equipment,
permits, safety, and timing from a locked source revision. Every element
links to screenplay evidence. Human verification is required before
declared completeness thresholds pass. Edits create inspectable ChangeSets
via `ProposalService`. Source changes label the derived projection stale.

## Commands

See `quality-commands.txt`. Headline: 12 focused tests passed; full pytest
761 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T00:15:46Z`
SHA: `1c4f232ac4955e53ff7039904912bbcda30d141d`
fingerprint: `56b8e678f1fa91b779fe0ae1ad352c2372069d9d12e702e21a5a6f18bfdf2a89`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Live Zoom/Meet and image-provider gates are owned by other packages.
