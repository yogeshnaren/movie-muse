# MM-003 — Professional screenplay document kernel — implementer evidence

Item: MM-003
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.document]`
- `src/movie_muse/document/**`
- `tests/document/**`

## What was built

Typed kernel over canonical `ScreenplayDocument`:
- immutable ChangeSet application (`insert/delete/update/move` block, insert scene, update metadata)
- NFC normalize, semantic validation, ID-based structural diff, selection anchors
- editor projection adapter (`movie-muse.editor.projection.v1`) that is never canonical
- replay/serialization determinism tests; dual dialogue, boneyard, Unicode, production metadata round-trip

Public surface: `movie_muse.document.api` only.

## Commands

See quality-commands.txt. Headline: document tests pass; full pytest passes after status-invariant toolchain test fix.

## Limitation

MM-001/MM-002 were marked STALE after the toolchain test change. Independent verification of MM-003 must wait until those dependencies are current PASS again.

## Verifier instructions

Do not verify MM-003 until MM-001 and MM-002 are current PASS. Then checkout the MM-003 commit, recompute fingerprint, run ruff/mypy/pytest including `tests/document`, and probe that mutating editor JSON does not change canonical `ScreenplayDocument`.
