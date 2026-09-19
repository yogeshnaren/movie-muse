# MM-013 — FDX compatibility program — implementer evidence

Item: MM-013
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-013.pass_record.

## Scope

`scope_keys: [module.fdx, test.fdx]`
- `src/movie_muse/fdx/**` public `movie_muse.fdx.api`
- `tests/fdx/**`
- `fixtures/fdx/**`

Did not edit MM-001 through MM-012 owned implementation files except MM-013
IN_PROGRESS bookkeeping (`movie_muse_build_status.yaml`, `docs/working-log.md`).
Did not add `fdx` to MM-001-owned `config/module-layout.yaml`. Did not
implement MM-014 or later. Did not mark PASS. Did not mark
`EXT-FDX-FINAL-DRAFT`.

## What was built

1. **Movie Muse FDX profile** `movie_muse_fdx` with deterministic UTF-8 XML
   (sorted attributes, two-space indent, `mm:` namespaced IDs).
2. **Lossless ScreenplayDocument ↔ FDX** adapters for text, scene IDs,
   notes, dual dialogue, production tags, revision marks, locked/omitted/A-B
   flags, attachments, spans, and unknown-safe extensions/attributes/child
   elements. Unsupported types are preserved as general + extras and
   disclosed on a `LossReport`.
3. **Fountain/plain-text** imports are explicitly lossy; empty LossReport is
   forbidden. **PDF** raises `PdfImportUnavailableError`. **Final Draft**
   live round-trip requires `MOVIE_MUSE_FINAL_DRAFT_BIN` and raises
   `FinalDraftUnavailableError` when unset (fail-closed, never `pytest.skip`).
4. **Fixture corpus** under `fixtures/fdx/` (ordinary, feature-complete,
   production, adversarial Unicode/RTL, unknown-extension) with `LICENSE.md`,
   `rights.yaml`, and `MANIFEST.yaml`. Files are original Movie Muse profile
   exports / authored samples, not competitor FDX.

## Commands

See `quality-commands.txt`. Headline (implementation commit
`65e4947ccf2ee4be0ee753ecdae571b77a83baf4`):

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend` | All checks passed |
| `python3 -m mypy src` | Success: 165 source files |
| `PYTHONPATH=src python3 -m pytest tests/fdx -q` | 26 passed |
| `PYTHONPATH=src python3 -m pytest tests/fdx tests/document tests/fixtures tests/harness --tb=no` | 64 passed |
| `PYTHONPATH=src python3 -m pytest --tb=no` | 491 passed, 1 warning |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-013` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `PYTHONPATH=src python3 scripts/mm_status.py fingerprint MM-013` | `8706e57d3591c583de0121cc715917748ca9ce0551f88ceec3f2eba07beae348` |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `65e4947ccf2ee4be0ee753ecdae571b77a83baf4`
Input fingerprint at `65e4947`: `8706e57d3591c583de0121cc715917748ca9ce0551f88ceec3f2eba07beae348`
UTC: `2026-09-01T18:10:19Z`

An evidence-only follow-up commit changes HEAD, so `fingerprint MM-013` at
the evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- Pagination / layout hashes are MM-014; this package does not fake them.
- `EXT-FDX-FINAL-DRAFT` stays `NOT_RUN` until a licensed Final Draft binary
  and real corpus exist. Unset `MOVIE_MUSE_FINAL_DRAFT_BIN` raises
  `FinalDraftUnavailableError`; it is not skipped.
- `movie_muse.fdx` is not listed in MM-001-owned `config/module-layout.yaml`
  so MM-001 PASS is not invalidated. Public surface is `movie_muse.fdx.api`.
- `verify_all.sh` remains fail-closed until later packages add named gates.
- Full pytest passed 491 tests with one unrelated HTTPX deprecation warning.

## Required external gates

`EXT-FDX-FINAL-DRAFT` (owner MM-013) remains `NOT_RUN`. A mock cannot satisfy
it. Do not mark it PASS.

## Verifier instructions

1. Fresh detached checkout of `65e4947ccf2ee4be0ee753ecdae571b77a83baf4` or
   this evidence commit. Recompute fingerprint MM-013 at that HEAD. At
   `65e4947` it must be
   `8706e57d3591c583de0121cc715917748ca9ce0551f88ceec3f2eba07beae348`.
   Do not edit the canonical ledger or `/workspace`.
2. Confirm MM-001 through MM-012 are current PASS and MM-013 is IN_PROGRESS
   with `pass_record: null`.
3. Run ruff, mypy src, focused pytest (`tests/fdx`), affected
   (`tests/fdx tests/document tests/fixtures tests/harness`), and full pytest
   (491).
4. Probes:
   - `FixtureCatalog` screenplays plus `fixtures/fdx/*.fdx` round-trip with
     no text/scene/note/tag/revision/lock/A-B/attachment loss on Movie Muse
     profile exports; unknown-extension fixture discloses and preserves.
   - Dual dialogue, notes, tags, revision marks, locked/omitted/A-B flags
     survive `export → import`.
   - Unicode/RTL fixture texts are identical after round trip.
   - Fountain/plain-text imports return a non-empty LossReport; PDF raises
     `PdfImportUnavailableError`; unset `MOVIE_MUSE_FINAL_DRAFT_BIN` raises
     `FinalDraftUnavailableError` (search the FDX tests for `pytest.skip(`;
     there must be none).
   - Repeated exports are byte-identical; host imports of `movie_muse.fdx.api`
     are allowed and `movie_muse.fdx.convert` is rejected.
   - FDX fixtures declare CC0, `allow_training: false`, and
     `copied_from_final_draft: false`.
5. Do not treat this implementer record as PASS.
