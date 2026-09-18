# MM-023 — Reference Lens — implementer evidence

Item: MM-023
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.reference_lens]`
- `src/movie_muse/reference_lens/**`
- `tests/reference_lens/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`ReferenceLensService` retrieves only rights-registered sources through
`RetrievalService`. Hits explain similarity, relevant passage, structure,
difference, counter-reference, rights, and why they surfaced. Queries that
ask for model training memory fail closed. The writer can disable the
lens and delete local reference indexes (tombstones). Citations resolve
through the rights registry.

## Commands

See `quality-commands.txt`. Headline: 7 reference_lens tests passed;
full pytest 652 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T21:20:44Z`

## Known limitations

- Local index deletion tombstones lens visibility; it does not rewrite
  the MM-017 retrieval blob index.
- Similarity is token-overlap, not an embedding model.
- `verify_all.sh` remains fail-closed until later named gates exist.
