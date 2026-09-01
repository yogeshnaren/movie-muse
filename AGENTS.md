# Movie Muse Agent Operating Contract

This file applies to the repository unless a more specific nested `AGENTS.md` adds stricter rules. V2 architecture, build plan, dependency DAG and status manifest are normative.

## Mission

Build a creator-controlled professional filmmaking workspace. Preserve creative agency, authorship, privacy, rights, provenance, deterministic screenplay fidelity and honest uncertainty.

## Before work

Read `README_HANDOFF.md`, `MOVIE_MUSE_V2_ARCHITECTURE.md`, `FEATURE_TRACEABILITY_AND_GAP_REVIEW.md`, `MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md`, `dependency_dag.yaml`, `movie_muse_build_status.yaml` and applicable Cursor rules. Run `python3 scripts/validate_handoff.py`. Inspect existing work and do not overwrite unrelated changes.

## Architecture rules

- Modular monolith plus durable worker; typed module interfaces; no cross-module table/internal imports.
- Typed ScreenplayDocument is canonical; editor and render formats are adapters.
- Local-first transactional save, immutable revisions and explicit merge/conflict semantics.
- Accepted canonical commands emit immutable ProjectEvents; CRDTs cannot bypass domain commands for semantic or operational state.
- AI/integrations produce proposals/candidates/draft artifacts; only authorized acceptance mutates canon.
- Enforce ACL and craft-decision ownership in application commands and worker commits.
- Route every model call through ModelRouter; record provenance, policy and costs.
- Preserve project/capability AI-off operation and local access through auth/subscription/provider outages.
- Derive incrementally through the dependency graph and label/block stale data appropriately.
- Use the generic artifact lifecycle for all specialized outputs.
- Never expose private chain-of-thought; provide evidence/method/assumptions/uncertainty instead.

## Change and verification rules

- Work only on DAG-runnable items.
- Tests and evidence are part of implementation.
- PASS requires a clean committed state and an independent verifier.
- Any relevant change invalidates the item and its transitive dependents to STALE.
- Never weaken, skip, quarantine or replace required tests with mocks to reach PASS.
- Never claim success when any item or required external gate is incomplete/stale.
- Preserve old pass evidence as history, but never treat it as current.

## Safety and product truth

- Do not commit secrets or log screenplay/private content by default.
- Do not train on user content without explicit separate consent and rights.
- Synthetic audiences are hypotheses; forecasts are scenarios; insurance output is readiness support.
- Role/device modes are projections of one canonical project; do not fork state or force identical cross-platform UI.
- Do not send correspondence or artifacts without preview and explicit authorized action.
- Do not copy competitor proprietary assets or UI; benchmark observable workflows.

## Final completion

Only `./scripts/verify_all.sh` may establish full completion. It must run from a clean checkout, fail closed, and print `MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS` only on total success.
