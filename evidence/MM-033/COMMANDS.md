# MM-033 — Visual Language and Color Intelligence — implementer evidence

Item: MM-033
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [capability.visual_language]`
- `src/movie_muse/visual_language/**`
- `tests/visual_language/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Advisory visual language: palettes, contrast/saturation/temperature, source
motivation, lighting ratios, production design, wardrobe, skin-tone rendering,
lens/render interaction, composition, temporal progression, rules/exceptions/
anti-rules/evolution. References must be RightsService-cited
(`PermittedUse.CITATION`). Export states correlation is not causation. Skin-tone
and accessibility review must pass. ShotIR `color_intent` updates are
inspectable proposals; only a human principal may ACCEPT. Integrations cannot
accept. No ChangeSet/ProposalService path.

## Commands

See `quality-commands.txt`. Headline: 21 focused tests passed; full pytest
869 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T02:36:16Z`
SHA: `b74386d8140132f6a72c4c07be8a1a9dd9b73868`
fingerprint: `793c7d81e3e9b3436ab61328d64a89a5da25553052d687c92d4b7ae211b8cb69`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- This package has no live external gate. Image/video rendering is MM-032/MM-034.
