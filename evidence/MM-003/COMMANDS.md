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

Follow-up after independent verifier FAIL at `222b2f6`: `structural_diff` now emits
sequence membership as `update_metadata.sequences`. `insert_scene` accepts `index`
and exact `scene_ids` replacement. Replay of the diff reproduces added, reordered,
and removed sequence scene IDs.

Public surface: `movie_muse.document.api` only.

## Commands

See quality-commands.txt. Headline after the sequence-diff fix: document tests pass
(21); full pytest passes.

## Verifier instructions

1. Fresh detached checkout of this commit. MM-001 and MM-002 must be current PASS.
2. Recompute `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-003`.
3. Run ruff, mypy, `pytest tests/document`, and full pytest.
4. Probe: target sequence with two scene IDs; `replay(structural_diff(source, target))`
   must retain both IDs and equal `normalize(target)` on sequences.
5. Probe reorder and removal of sequence membership the same way.
6. Probe that mutating editor JSON does not change canonical `ScreenplayDocument`.
7. Do not edit the canonical ledger.
