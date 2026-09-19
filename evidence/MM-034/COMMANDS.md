# MM-034 — Video previs provider workflow — implementer evidence

Item: MM-034
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.video_previs]`
- `src/movie_muse/video_previs/**`
- `tests/video_previs/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

ShotIR/storyboard sequences queue through JobService with a human consent
gate, ModelRouter cost preflight, durable retry, cancel, progress, and
local `generate_text` complete into generic media artifacts. Accepted
clips are reused on identical fingerprints. Timeline/animatic assembly
uses package artifacts. Intended-effect review is human-only and cannot
promote generated video to canon. `EXT-VIDEO-PROVIDER` stays NOT_RUN;
live render is fail-closed and is not claimed as sandbox smoke.

## Commands

See `quality-commands.txt`. Headline: 23 focused tests passed; full pytest
911 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T03:35:00Z`
SHA: `1aa483e94022d3b7a23df1bc963108f767b4b48c`
fingerprint: `16cbc9a6663804045db5ad58120dffa8efb5fa803a2b9f9060640ecbb13f592b`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Live video-provider smoke is not claimed; mocks do not satisfy
  EXT-VIDEO-PROVIDER.
