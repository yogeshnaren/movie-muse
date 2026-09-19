# MM-041 — Rubric and scene/script analysis — implementer evidence

Item: MM-041
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.rubric]`
- `src/movie_muse/rubric/**`
- `tests/rubric/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Configurable evidence-linked rubrics for clarity, character, pacing, theme,
emotion, producibility, and intended effect. Human and model raters, visible
disagreement, counter-evidence, and human-only creator overrides. Unexplained
scalar scores fail closed. Score changes trace to inputs, model, and rubric
version. Analysis is labeled advisory and does not write FilmIR,
CreativeIntentIR, or ChangeSets.

## Commands

See `quality-commands.txt`. Headline: 21 focused tests passed; full pytest
953 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T04:40:00Z`
SHA: `f441f921d4b522e1e7d571ccfbf513a07acd66e9`
fingerprint: `33783183f28107c087984db2ee6c7540092e50ef84b7567c495db34adb565b19`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Deterministic fixture `generate_text` ratings are not live expert measurement.
