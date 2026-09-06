# Competitive workflow protocol

Owner: MM-016  
Dated: 2026-09-05

## Automation

From the repository root:

```
PYTHONPATH=src python3 -m pytest tests/competitive -q
```

Every `result: supported` row must name an existing pytest node in
`docs/competitive/workflow-matrix.yaml` `automation`. Those tests fail the
suite when the observable criterion regresses. That is the release-blocking
automation.

## Manual / external

| Row | Protocol |
|---|---|
| `FD-FDX-LICENSED` | Set a real `MOVIE_MUSE_FINAL_DRAFT_BIN`, run the licensed corpus, attach the human review report, then move `EXT-FDX-FINAL-DRAFT` off `NOT_RUN`. Unset binary must keep raising `FinalDraftUnavailableError`. Never mock the gate. |

Gap rows are not automatable yet. Their `awaiting` package owns the later
implementation. Documenting the gap is required; inventing a catalog or
live collaborator is forbidden.

## Fixtures

Reuse MM-012 screenplay fixtures (`small_kitchen`, `feature_complete_harbor`,
`production_locked_sides`). Do not add `fixtures/**` from this package.

## Truthfulness

- Do not claim Movie Muse matches a named product’s UI or feature set.
- `supported` is a Movie Muse capability statement.
- Licensed Final Draft inspection stays `EXTERNAL` until real evidence exists.
