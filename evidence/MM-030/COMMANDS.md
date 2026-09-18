# MM-030 — Beat frameworks and completion tracking — implementer evidence

Item: MM-030
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.beats]`
- `src/movie_muse/beats/**`
- `tests/beats/**`

Did not add `fixtures/**`. Did not mark PASS.

## What was built

`BeatService` provides configurable beat frameworks. Three-movement and custom
frameworks are permitted with original labels. Named Save-the-Cat and Hero's
Journey templates require a licensed/permitted rights source and use original
story-function keys; this package does not embed third-party workbook prose.
Mappings are guidance, not prescriptive truth (`formula_score` is always null).
Manual override wins over suggestions. `not applicable` is supported and
excluded from completion ratio. Accessible themes meet a 4.5:1 contrast floor
and include pattern plus text labels. Mapping changes invalidate dependent
analysis through `DependencyEngine.invalidate_inputs`.

## Commands

See `quality-commands.txt`. Headline: 16 focused tests passed; full pytest
734 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-18T23:28:09Z`
SHA: `cd88f34562daeda561089d54c9a054ae7a2ccabf`
fingerprint: `738578f9e62eae6e18478a4afba3e0839189786469db6fc6b160e998746293e1`

## Known limitations

- Named licensed templates are identifiers plus original story-function keys;
  they do not reproduce copyrighted beat-sheet text even when rights exist.
- `verify_all.sh` remains fail-closed until later named gates exist.
