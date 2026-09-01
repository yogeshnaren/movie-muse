# Cursor Master Execution Prompt — Movie Muse V2

Use this prompt as a persistent repository objective. Do not treat it as a request to merely scaffold files or summarize the plan.

## Objective

Implement and independently verify the complete Movie Muse working prototype defined by the V2 handoff package. Preserve creator-first control, all 47 feature packages, professional screenplay/production compatibility, local-first operation, and truthful evidence boundaries.

Do not declare success, stop successfully, or print the final PASS sentinel until every required work package is current PASS and `./scripts/verify_all.sh` succeeds from a clean checkout.

## Mandatory reading order

Read completely before editing:

1. `AGENTS.md` and all applicable nested `AGENTS.md` files.
2. `.cursor/rules/00-movie-muse-core.mdc`.
3. `.cursor/rules/10-verification-and-status.mdc`.
4. `MOVIE_MUSE_V2_ARCHITECTURE.md`.
5. `FEATURE_TRACEABILITY_AND_GAP_REVIEW.md`.
6. `MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md`.
7. `dependency_dag.yaml`.
8. `movie_muse_build_status.yaml` and its schema.
9. This prompt.

These V2 files form one specification. Resolve apparent ambiguity by choosing the interpretation that preserves domain invariants, creator control, data integrity, professional interchange, least privilege, deterministic behavior and stronger verification. Record material decisions in ADRs. Do not import superseded V1 sequencing or mutable-state assumptions.

## Bootstrap actions

1. Run `python3 scripts/validate_handoff.py`; repair handoff inconsistencies before product work.
2. Inspect the repository and preserve unrelated/user changes.
3. Record the clean baseline commit in `movie_muse_build_status.yaml`.
4. Create `config/verification-scopes.yaml`, mapping every manifest `scope_key` to exact owned/shared paths. Fail on empty/unmatched scopes once the relevant package exists.
5. Implement a status tool that validates the schema/DAG, computes fingerprints, selects runnable items, marks PASS/STALE, and recursively invalidates dependent closure.
6. Create the real repository `scripts/verify_all.sh` early. It may initially fail, but must fail closed and grow with each package.
7. Create the golden fixtures in MM-012 before accepting FDX/layout/editor/AI work.

## Work selection

Use `dependency_dag.yaml`, not intuition or file order. Select only an item whose direct dependencies are current PASS. Prefer critical foundations and unblock the critical path. Parallel work is allowed only for independent nodes and isolated file ownership; merge results through the same tests and status rules.

Never bypass a prerequisite to demonstrate downstream UI. Never add placeholder success, unconditional skips, hard-coded golden outputs, or tests that only assert mocks were called.

## Per-item execution loop

For each work package:

1. Move it from `NOT_STARTED`/`FAIL`/`STALE` to `IN_PROGRESS`; record owner and UTC start in the working log.
2. Re-read its full plan acceptance and relevant architecture sections.
3. Inspect dependencies, current repository state and tests.
4. Implement a real vertical slice including migrations, domain/application/UI boundaries, errors, accessibility, observability, security/rights and documentation appropriate to risk.
5. Run focused unit/property tests, then integration and actual user-flow tests.
6. Run affected regression, migration, security, provider and platform suites.
7. Debug root causes and retest until clean. Do not weaken acceptance or tests to force green.
8. Commit the exact verified implementation and ensure required evidence is committed or content-addressed by an immutable reference.
9. Compute its input fingerprint from its resolved scope, shared inputs, verifier code and direct dependency fingerprints.
10. Hand the committed item to `.cursor/agents/independent-verifier.md`. The verifier must not be the implementer, must start from written criteria and a clean environment, and must rerun commands rather than accept screenshots or claims.
11. On verifier failure, set FAIL, record root cause, fix, recommit and repeat verification.
12. Only after independent PASS, populate the manifest `pass_record` and set PASS.
13. Recompute staleness/dependent closure after every code, schema, fixture, lockfile, configuration, prompt, policy, test or verifier change.

## Commit-bound PASS and invalidation

PASS is evidence at one commit/input fingerprint, not a permanent checkbox.

Before and after each change:

- map changed files to scope keys;
- compare affected item fingerprints;
- mark directly affected PASS items STALE;
- traverse reverse DAG edges and mark every transitive dependent STALE;
- clear/retain old pass records as historical evidence, but never treat them as current;
- queue reverification in topological order.

If a changed file matches no scope, fail and update the scope mapping. If a prerequisite is not current PASS, a dependent cannot be PASS. Reverting a file never restores PASS automatically.

## Required architectural constraints

- Canonical screenplay state is the typed `ScreenplayDocument`, never editor-framework JSON.
- Preserve authored, structural, inferred, operational and scenario epistemic types; never silently promote one into another.
- Layout/pagination is deterministic and platform-independent with pinned font metrics.
- Production revisions include locks, colors/sets/marks, changed pages, A/B material, omitted scenes and sides.
- Revisions, checkpoints, proposals, artifact versions and merges are immutable/auditable; accepted commands emit immutable ProjectEvents.
- AI, rooms and integrations propose; authorized humans accept into canon.
- Local save commits before acknowledgement; offline edit/export works even through auth/subscription/sync/AI outages; conflicts never use silent last-write-wins.
- ACL and craft ownership are enforced at every command and worker side effect, including branch protection and sensitive finance/rights access.
- Build a modular monolith plus durable workers. Do not create internal microservices without an approved evidence-based ADR.
- The ModelRouter must mediate every model call and exist before extraction/generation.
- AI is optional at project/capability level; role contracts distinguish experience/actor, audience, expert/researcher, divergence, executor and production analysis.
- Rights/lineage/EvidenceBundle accompany consequential outputs. Do not expose hidden chain-of-thought.
- Generic artifacts precede specialized storyboards, correspondence, insurance packets and investor decks.
- Production order is breakdown -> schedule -> budget -> insurance readiness.
- CRDTs may coordinate authored document/comments/cursors/presence only; semantic/production/financial mutations use validated commands/events.
- Role/device modes are projections over one project; mobile job design and field latency matter more than identical desktop UI.
- SceneSpace/ShotIR is deterministic and provider-independent; visual renderers honor locked properties and show cost before paid work.
- Stale derived data may be viewed only when unmistakably labeled and may not silently feed consequential exports.

## AI and claims policy

Use deterministic test doubles for repeatable contract tests and real configured provider calls for required external smoke tests. Store capability, provider/model/version, policy route, template/prompt version, input hashes, cost/latency, consent and result provenance. Never log private screenplay text by default.

Fine-tuning is conditional on MovieMuse Bench showing benefit over prompt/retrieval baselines and on explicit rights/consent. Benchmark complete task configurations, separately evaluating objective correctness, blinded creative preference and workflow utility. Local models are ModelRouter routes with the same evaluation, safety and provenance requirements.

Synthetic audience calls are hypotheses, not independent human samples. Forecasts are scenarios, not guarantees. Insurance artifacts are readiness support, not underwriting/coverage. Generated emails/messages/decks require review and explicit authorized delivery.

Track correction minutes, retained suggestion rate, post-accept edit distance, false-critical alerts, regeneration-to-acceptance and Creator Leverage Ratio. Acceptance clicks and favorable surveys do not prove value.

## External prerequisites

Never invent credentials or conceal an unavailable provider. Contract tests may pass with deterministic doubles, but record `BLOCKED_EXTERNAL` for the owner item when a required live/sandbox gate cannot run. Include the exact gate, attempted command, safe error summary, required user/admin action and whether alternate meaningful work remains.

A final-required gate cannot be waived by the implementation agent. Only a documented product-owner scope amendment can change `required_for_final`, and that change invalidates the plan/manifest/final-gate verification.

## Competitive and compatibility verification

Maintain the dated workflow matrix for Final Draft, Celtx, Arc Studio, Filmustage and Scriptation. Benchmark observable tasks, not proprietary UI. Never claim parity without evidence.

FDX must pass semantic and production round trips, deterministic exports, explicit unknown/loss behavior, reference renders and licensed/manual Final Draft corpus inspection. “The file opens” is insufficient.

Maintain real-project product-validation protocols for the authoring switch/sidecar hypothesis, Divergence Engine, Room Harvest, continuity/breakdown, SceneSpace control, budget calibration and audience calibration. Failed PMF gates narrow/resequence commercial release; never rewrite implementation status to hide them.

## Independent verifier contract

The verifier must:

- be a separate agent/person from the implementer;
- receive acceptance criteria, commit and reproducible commands, not private reasoning;
- use a clean checkout/database/cache and fresh fixtures;
- test negative, failure, offline, concurrency, stale and authorization behavior appropriate to risk;
- inspect user-visible behavior and evidence, not only unit tests;
- record identity, independence basis, environment, commit, commands, results, evidence paths and limitations;
- return FAIL on skipped required checks, dirty state, missing evidence or unreproducible instructions.

The parent/implementer may not override a verifier FAIL by editing the manifest.

## Final gate

MM-047 begins only after MM-001 through MM-046 are current PASS. From a clean checkout and documented environment, `./scripts/verify_all.sh` must validate all layers listed in the build plan, all required external gates and the 41-step same-project golden journey.

The script must fail on missing tools, skips, stale items, dirty generated outputs, manifest/DAG/schema mismatch, unavailable required providers, test failure or absent evidence. It must never print the success sentinel early or from a trap. Only a fully successful run may end with:

```text
MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS
```

Record the final commit, environment, complete log/checksum and independent verifier result in MM-047. Then—and only then—report completion with a concise list of delivered capabilities, limitations, external evidence and exact reproduction command.

## Persistence instruction

Continue implementing, debugging and verifying while safe in-scope work remains. Do not stop because a first attempt fails or because the context is long. When externally blocked, complete all independent runnable work, record precise blockers, and report that the prototype is not complete. Never convert incomplete states to PASS to satisfy the terminal instruction.
