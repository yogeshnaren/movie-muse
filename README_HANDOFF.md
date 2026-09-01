# Movie Muse V2 — Cursor Handoff

Package version: `2.1.0`  
Status: architecture/build handoff; implementation has not started  
Canonical manifest: `movie_muse_build_status.yaml`

## Start here

Cursor must read these files, in order, before changing product code:

1. `AGENTS.md`
2. `.cursor/rules/00-movie-muse-core.mdc`
3. `MOVIE_MUSE_V2_ARCHITECTURE.md`
4. `FEATURE_TRACEABILITY_AND_GAP_REVIEW.md`
5. `MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md`
6. `dependency_dag.yaml`
7. `movie_muse_build_status.yaml`
8. `CURSOR_MASTER_EXECUTION_PROMPT.md`

Then execute the master prompt. The YAML manifest is the only completion ledger. Prose checklists are explanatory and may not override it.

## What V2 corrects

- Replaces rich-text-as-domain-model with a professional, typed screenplay document kernel.
- Makes offline/local-first persistence authoritative on-device, with an outbox/inbox sync protocol and deterministic conflict handling.
- Specifies deterministic layout, pagination, locked pages, scene numbering, revision colors, revision marks, A/B pages and scenes, omitted scenes, and production sides.
- Replaces mutable snapshots with immutable `Revision`, `Branch`, `Checkpoint`, `ChangeSet`, and auditable `Merge` objects.
- Makes Branch/Revision/Merge and project/document/branch ACLs first-class application semantics.
- Uses a modular monolith plus transactional outbox and durable workers; internal microservices are prohibited until measured scaling or isolation evidence justifies extraction.
- Adds a machine-enforceable dependency DAG, cycle checks, dependency-closure scheduling, and dependent-closure invalidation.
- Corrects build order: golden fixtures early; model router before AI extraction; generic artifacts before specialized outputs; schedule before budget; budget before insurance.
- Makes every PASS commit-bound. Relevant source, fixture, schema, dependency-lock, configuration, or verifier changes convert affected PASS records to STALE, recursively through dependents.
- Requires independent verification and competitive regressions for Final Draft, Celtx, Arc Studio, Filmustage, and Scriptation workflows.
- Raises FDX acceptance from “file opens” to semantic and production-script round-trip fidelity.
- Ends with one fail-closed `./scripts/verify_all.sh` gate that must print exactly `MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS` and exit 0.
- Adds the reference-audit corrections: ProjectEvent history, epistemic type separation, CRDT boundaries, craft-owner modes, AI-off/auth-outage guarantees, nested beliefs, semantic annotation anchors, SceneSpace, MovieMuse Bench, cost/correction metrics, budget maturity, specialist Integration Mesh and PMF falsification gates.

## Source preservation note

The requested `/mnt/data` mount was not present in this workspace, and the referenced task no longer exposed its generated attachments. V2.0 reconstructed the package from the retained 47-package inventory. V2.1 additionally checked the supplied Deep Research/PMF report, Voice of Filmmaker corpus and both pasted prior analyses. No original file was overwritten. If older plan/manifest copies are later recovered, retain them under `docs/archive/v1/`; do not merge their rules back unless all V2.1 invariants remain true.

## Non-negotiable product principles

1. The creator is the author and final decision-maker. AI proposes; it never silently mutates canon.
2. Conversation, model inference, and generated media are candidates until a permitted human explicitly accepts them.
3. Consequential outputs carry evidence, provenance, uncertainty, rights, model/version, and human-validation state—not hidden chain-of-thought.
4. Local authoring continues without network access. Cloud and third-party features degrade honestly.
5. A prototype feature is complete only when its real vertical slice works end to end and its limitations are labeled truthfully.
6. Synthetic audience hypotheses are not human audience research. Forecasts are scenarios, not guarantees. Insurance output is readiness material, not underwriting or coverage.

## Package map

- `MOVIE_MUSE_V2_ARCHITECTURE.md` — normative domain and system specification.
- `MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md` — all 47 work packages, acceptance standards, and golden path.
- `CURSOR_MASTER_EXECUTION_PROMPT.md` — persistent execution contract for Cursor.
- `CURSOR_AUTONOMOUS_RUNBOOK.md` — exact Cloud Agent, `/goal`, worktree, verifier and credit-usage operating procedure.
- `movie_muse_build_status.yaml` — mutable, machine-readable completion ledger; all items start `NOT_STARTED`.
- `dependency_dag.yaml` — canonical dependency graph and invalidation inputs.
- `DEPENDENCY_GRAPH.md` — human-readable graph and critical path.
- `FEATURE_TRACEABILITY_AND_GAP_REVIEW.md` — all 14 additions mapped to architecture/work packages and every source-derived correction.
- `QA_REPORT.md` — cross-file validation result, coverage audit, and known source limitation.
- `schemas/build-status.schema.json` — status-manifest schema.
- `AGENTS.md`, `.cursor/rules/*`, `.cursor/agents/*` — repository and agent operating rules.
- `scripts/validate_handoff.py` — static consistency and DAG validator for this handoff.
- `scripts/verify_all.sh` — fail-closed final-gate starter; it intentionally fails until Cursor implements every named gate.

## Bootstrap into a repository

Copy the contents of this directory to the repository root, preserving hidden paths. Do not copy over a repository-specific `AGENTS.md` without reconciling it. Keep `movie_muse_build_status.yaml` under version control. Run:

```bash
python3 scripts/validate_handoff.py
```

The handoff validator requires Python 3, PyYAML, and `jsonschema`.

Before implementation begins, Cursor must record the repository baseline commit in the manifest. Every completed work package must record its own verification commit, evidence paths, commands, verifier identity, and UTC timestamp.

## Definition of final completion

The package is not an assertion that Movie Muse has been built. The supplied `verify_all.sh` intentionally reports `NOT_READY` until all gate scripts exist and pass. The implementation is complete only when:

- every required manifest item is `PASS` at the current commit;
- no item is `NOT_STARTED`, `IN_PROGRESS`, `FAIL`, `BLOCKED_EXTERNAL`, or `STALE`;
- no dependency is incomplete or stale;
- all external-live gates designated `required_for_final: true` have genuine sandbox/live evidence;
- an independent verifier reproduces every critical and high-risk acceptance flow;
- a clean checkout runs `./scripts/verify_all.sh` successfully; and
- its final output line is exactly `MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS`.
