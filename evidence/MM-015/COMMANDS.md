# MM-015 — Professional editor and offline authoring UX — implementer evidence

Item: MM-015
Role: implementer. This record is NOT a PASS record and does not set
`movie_muse_build_status.yaml` items.MM-015.pass_record.

## Scope

`scope_keys: [app.editor, ux.authoring]`
- `src/movie_muse/editor/**` public `movie_muse.editor.api`
- `apps/editor/**` thin local host
- `frontend/src/editor/**` keyboard-first authoring surface
- `tests/editor/**`, `tests/ux/authoring/**`

Did not add `editor` to MM-001-owned `config/module-layout.yaml`.
Did not add `fixtures/**`. Did not implement MM-016 or later. Did not mark PASS.

## What was built

1. **EditorService** over `RevisionService`. Every keystroke becomes a
   ChangeSet or an explicit revision command. Editor JSON
   (`movie-muse.editor.projection.v1`) is a projection only;
   `reject_editor_json` fails closed.
2. **Keyboard transitions** Enter/Tab emit `INSERT_BLOCK` ChangeSets with
   required character_cue / dialogue_pair / scene ids.
3. **Undo/redo**, search/replace, authored autocomplete, outline/cards,
   notes, checkpoint/branch/diff, preserve/explore/lock/intent.
4. **Airplane / outage local save** remains available. Recovery journal
   in `workspace_meta` replays unacked keystrokes without double-apply.
5. **Accessibility contract** uses layout reading order.
   Distraction-safe author mode does not fork project state.
6. **Frontend** keyboard-first screenplay pane, outline, cards, notes,
   revision command history, airplane banner, ARIA application role.
7. **Host** `apps/editor` binds `EditorService` only through public APIs.

## Commands

See `quality-commands.txt`. Headline results:

| Command | Result |
|---|---|
| `python3 scripts/validate_handoff.py` | `HANDOFF_VALIDATION=PASS` |
| `python3 -m ruff check src tests scripts backend apps` | All checks passed |
| `python3 -m mypy src` | Success: 193 source files |
| `PYTHONPATH=src python3 -m pytest tests/editor tests/ux/authoring -q` | 28 passed |
| `PYTHONPATH=src python3 -m pytest tests/editor tests/ux/authoring tests/document tests/revisions tests/layout -q` | 86 passed |
| `PYTHONPATH=src python3 -m pytest --tb=no` | 543 collected / 543 passed, 2 warnings |
| `cd frontend && npm test -- --run` | 8 passed |
| `PYTHONPATH=src python3 scripts/mm_status.py validate` | `STATUS_VALIDATE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py check-scopes` | `SCOPE_COVERAGE=PASS` |
| `PYTHONPATH=src python3 scripts/mm_status.py runnable` | `MM-015` |
| `PYTHONPATH=src python3 scripts/mm_status.py boundaries` | 0 violations |
| `PYTHONPATH=src python3 scripts/mm_status.py secrets` | 0 hits |
| `./scripts/verify_all.sh` | fail-closed missing `migrations_backup_and_recovery` |

Implementation commit: `4c6ba75`
UTC: `2026-09-05T23:50:00Z`

An evidence-only follow-up commit changes HEAD, so fingerprints at the
evidence commit will differ because `verification_commit` is hashed.

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Frontend session reducer is a local command adapter for keyboard UX
  tests; durable canon writes are `EditorService` / `RevisionService`.
- Pixel/bitmap editor chrome is not a layout engine. Pagination stays
  `movie_muse.layout`.
- `EXT-FDX-FINAL-DRAFT` stays `NOT_RUN`.

## Required external gates

None owned by MM-015.
