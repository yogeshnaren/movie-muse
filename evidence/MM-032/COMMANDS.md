# MM-032 — Storyboard generation and annotation — implementer evidence

Item: MM-032
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.storyboard]`
- `src/movie_muse/storyboard/**`
- `tests/storyboard/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Diagrammatic ShotIR storyboards via ModelRouter `generate_text` and generic
media artifacts. Frames link to shot identity and source revision. Locked
ShotIR attributes fail closed on drift. Accepted assets are reused on
identical input fingerprints. Regeneration, compare, correction burden, and
distinct director/producer/writer annotations are recorded. Scene changes
mark linked storyboards stale. `EXT-IMAGE-PROVIDER` stays NOT_RUN; live
render is fail-closed and is not claimed as sandbox smoke.

## Commands

See `quality-commands.txt`. Headline: 19 focused tests passed; full pytest
888 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T02:58:00Z`
SHA: `e43fe5729d713830a065fe324da3f0f195b9ba2d`
fingerprint: `91b406ce6eee896997dd80ec760ff8a3d955e1e9d838e4b4f29ba0f539bce832`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Live image-provider smoke is not claimed; mocks do not satisfy
  EXT-IMAGE-PROVIDER.
