# MM-040 — Audience Resonance Lab — implementer evidence

Item: MM-040
Role: implementer. This record is NOT a PASS record.

## Scope

`scope_keys: [module.audience_lab]`
- `src/movie_muse/audience_lab/**`
- `tests/audience_lab/**`

Did not add `fixtures/**`. Did not mark PASS. Did not edit `module-layout.yaml`.

## What was built

Evidence-tiered Audience Resonance Lab. Synthetic LLM personas are hypotheses
and are never human/bootstrap population samples. Human tiers (expert/reader,
table-read/panel, previs screening, released outcome) require consent and
RightsService provenance. Repeatability, prompt perturbation, variance,
within-lab calibration residuals, and advisory intended-effect comparison
are recorded.

## Commands

See `quality-commands.txt`. Headline: 21 focused tests passed; full pytest
932 passed; ruff/mypy clean; verify_all fail-closed at
`migrations_backup_and_recovery`.

UTC: `2026-09-19T04:05:00Z`
SHA: `2a634573652e60a9017d03ea7089cbd4c20b2e00`
fingerprint: `86a70a277114a30407ceabad218472880ceb70b1210f913e29deb74b95f8709e`

## Known limitations

- `verify_all.sh` remains fail-closed until later named gates exist.
- Deterministic fixture experience scores are not live audience measurement.
