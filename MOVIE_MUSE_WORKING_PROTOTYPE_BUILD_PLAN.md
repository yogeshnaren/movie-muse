# Movie Muse Working Prototype — Corrected V2 Build Plan

Version: `2.1.0`  
Work packages: 47 required  
Canonical status/dependencies: `movie_muse_build_status.yaml` and `dependency_dag.yaml`

## 1. Outcome and execution policy

Build a truthful, working vertical-slice prototype for Web, macOS, Windows, iPhone, and Android. All named feature families remain in scope. “Prototype” permits limited scale, fixture-backed datasets, and clearly labeled provider constraints; it does not permit fake UI, silent mocks, unimplemented buttons, false accuracy claims, or marking unavailable live integrations PASS.

The delivery loop for every package is:

```text
implement -> test -> debug -> retest -> integration test -> user-flow test
          -> regression/security checks -> independent verification -> PASS
```

Implementation alone is not completion. Each PASS is bound to a commit and input fingerprint. Relevant changes invalidate the item and its transitive dependents to STALE.

The 47-package prototype is broader than the recommended first commercial release. Delivery stages are evidence-gated: creator revision wedge first; room/director second; production translation third; audience/commercial intelligence as a research track. Prototype completion proves vertical slices and architecture—it does not justify launching every feature simultaneously or making accuracy/PMF claims.

## 2. Global Definition of Done

A work package may move to PASS only when all of the following are true:

1. Every declared dependency is PASS at compatible verification commits.
2. Code, migrations, documentation, telemetry, error states, and accessibility are implemented.
3. No acceptance criterion is waived, commented out, quarantined, or satisfied only by a mock unless the criterion explicitly says deterministic test double.
4. Required unit, property, integration, E2E, regression, security/rights, and platform tests pass.
5. Real user-visible behavior was exercised from a clean supported environment.
6. Evidence paths, exact commands, result summaries, commit SHA, input fingerprint, UTC time, and independent verifier identity are in the manifest.
7. The independent verifier reproduced the acceptance flow and recorded PASS.
8. Known limitations are truthful, user-visible where relevant, and do not violate required acceptance.

`BLOCKED_EXTERNAL` is not PASS. A deterministic provider double may validate contracts while a required sandbox/live test remains blocked. Overall completion requires every `required_for_final: true` external gate to pass.

## 3. Milestones and work packages

### Milestone A — Repository and domain foundations

#### MM-001 Repository, toolchain, and quality baseline

Create the monorepo/module layout, pinned runtimes/package managers, formatting/lint/type checks, test layers, reproducible development environment, CI skeleton, secret-safe configuration, and ADR template. Establish module-boundary tests and artifact/evidence directories.

Acceptance: clean bootstrap works on a second environment; lockfiles are committed; CI fails on lint/type/test/schema/DAG errors; no real secret appears in source or logs.

#### MM-002 Domain constitution and versioned schemas

Define versioned schemas and invariants for Project, ScreenplayDocument, FilmIR, CreativeIntentIR, ProjectMemory, Proposal, ChangeSet, ProjectEvent, EvidenceBundle, RightsRecord, CollaborationEvent, ShotIR/SceneSpace, production projections, scenarios, artifacts, and dependency nodes. Make authored, structural, inferred, operational and scenario epistemic types non-interchangeable.

Acceptance: schemas have valid/invalid fixtures, compatibility policy, migration hooks, stable ID rules, and generated types tested across application boundaries.

#### MM-003 Professional screenplay document kernel

Implement the typed screenplay AST/tree, stable node identities, typed operations, normalization, semantic validation, structural diff, selection anchors, and adapters for the chosen editor UI.

Acceptance: property tests prove operation replay and serialization determinism; all professional block types, dual dialogue, notes, boneyard, Unicode and production metadata round-trip without using editor JSON as canonical state.

#### MM-004 Local-first persistence, migrations, and sync primitives

Implement the embedded transactional database, content-addressed blobs, crash-safe save, local outbox/inbox, idempotent operation envelopes, migration system, backup/export, corruption recovery, and offline status UX.

Acceptance: airplane-mode open/edit/save/reopen/export succeeds; authentication/subscription/sync/AI outage cannot lock already-local work; local/sync/backup/conflict state is unambiguous; forced termination cannot lose an acknowledged save; migrations, old-version recovery and restoration are tested; duplicate/out-of-order envelopes are safe.

#### MM-005 Immutable revisions, branches, checkpoints, ChangeSets, and merges

Implement immutable content-addressed revisions, named branches, checkpoints, branch protection, structural three-way merge, conflict records/resolution, proposal rebasing, history/diff UI, and restore-via-new-revision.

Acceptance: no history object is mutated; accepted commands emit replayable ProjectEvents; concurrent non-overlapping edits merge; conflicts fail closed; stale proposals cannot apply; checkpoints remain fixed; branch/merge/event audit is reproducible.

#### MM-006 ACL, tenancy, audit, and collaboration semantics

Implement project/document/branch/artifact/operation permissions, roles, craft-decision ownership, Writer/Director/Producer/AD/Room/Department/Investor/Field projections, custom mode composition, invitation/membership state, protected-branch approvals, ACL epochs, append-only audit, and offline revocation quarantine.

Acceptance: deny-by-default server/authority and worker checks; tenant-isolation and confused-deputy tests; revoked offline edits are preserved locally but cannot upload; sensitive budget/rights data is separately permissioned; AI cannot confirm a department-owned craft decision; modes never fork project state.

#### MM-007 Generic artifact subsystem

Implement Artifact, immutable ArtifactVersion, Template, Render, Link, DeliveryRecord, review state, provenance/evidence links, reproducible rendering, storage, preview, export, and audited delivery.

Acceptance: a generic document, table, media and package artifact can be versioned, regenerated, compared, reviewed, exported and linked to a source revision without specialized storage paths.

#### MM-008 Durable worker and transactional job infrastructure

Implement durable queue/leases, transactional outbox/inbox, idempotency, retries/backoff, heartbeats, timeouts, cancellation, dead letters, priorities, cost quotas, progress, tracing and crash recovery.

Acceptance: kill/restart and duplicate-delivery tests show no duplicate canonical mutations; failed jobs are explainable/retryable; worker rechecks ACL and input freshness before committing results.

#### MM-009 Model router, provider adapters, local models, and policy

Implement capability-based routing across deterministic doubles, local models and remote providers; project/capability AI-off controls; explicit actor/audience/expert/researcher/divergence/executor/production-analyst contracts; consent/data-classification policy; preflight cost quote and actual usage; cost/latency budgets; cache/reuse policy; structured outputs; fallback; prompt/template registry; model provenance; and fine-tuned-adapter interface.

Acceptance: routing decisions are policy-tested and auditable; professional non-AI authoring remains functional with AI disabled; offline-safe routes work; unavailable or disallowed providers fail honestly; paid operations require visible authorization; extraction packages cannot import provider SDKs directly; real configured provider smoke test is recorded.

#### MM-010 Rights registry, provenance, sources, and Evidence Bundles

Implement rights/source registry, permitted-use policy, citations, EvidenceBundle, input lineage, human-validation state, uncertainty, counter-evidence, and export disclosures.

Acceptance: unlicensed/disallowed source use is blocked; every consequential AI/forecast output links to permitted evidence and model/method provenance; no UI claims to expose hidden chain-of-thought.

#### MM-011 Machine-enforceable dependency and invalidation engine

Implement typed dependency nodes/edges, content/config/model input hashes, minimal invalidation frontier, transitive dependent-closure staleness, recomputation queueing, cycle prevention, and current/stale UI state.

Acceptance: property tests compare incremental results with clean full recomputation; relevant input changes stale exactly the dependent closure; stale outputs cannot masquerade as current.

### Milestone B — Compatibility and editor confidence

#### MM-012 Golden fixtures and test harness

Create small/feature-complete/production/adversarial screenplay fixtures, deterministic expected AST/layout/IR artifacts, provider recordings/doubles, rights fixtures, golden-path project seed, and MovieMuse Bench registry before AI extraction work. Separate objective-ground-truth tasks, blinded human creative preference, and observed workflow-utility evaluations.

Acceptance: fixture/data licenses and consent are recorded; golden updates require explicit review; nondeterminism detection runs repeated builds; fixtures cover every production-script edge; benchmark tasks score complete configurations rather than model names and cannot collapse into one universal MovieMuse score.

#### MM-013 FDX compatibility program

Implement schema/profile validation, lossless import/export adapters, unknown-safe extension preservation, explicit loss reports, deterministic exports, and round-trip corpus automation.

Acceptance: zero text/scene/structural loss; notes, dual dialogue, tags, revisions, locked pages, omitted and A/B material preserved; Final Draft round-trip/manual corpus evidence recorded; unsupported data is preserved or disclosed before save/export.

#### MM-014 Deterministic layout, pagination, and production revisions

Implement pinned font metrics/layout engine, structured layout traces, page/line breaking, headers/footers, MORE/CONT'D, paper profiles, locked pages/scenes, revision sets/colors/marks, changed pages, A/B pages/scenes, omitted scenes, sides, clean/revision exports.

Acceptance: identical input hashes produce identical layout hashes across all five platforms; reference renders pass tolerances; locked production semantics survive edits, merges and FDX round trips.

#### MM-015 Professional editor and offline authoring UX

Implement keyboard-first screenplay editing, element transitions, autocomplete, undo/redo, search/replace, outline/cards, comments/notes, revision views, autosave, branch/checkpoint/diff flows, contextual selection for preserve/explore/lock/intent operations, accessibility, recovery and distraction-safe author mode.

Acceptance: complete scene authoring and revision work in airplane mode; no keystroke loss under stress; keyboard/accessibility flows pass; editor cannot bypass document/revision commands.

#### MM-016 Competitive workflow regression suite

Codify non-infringing task-level regressions against professional expectations represented by Final Draft, Celtx, Arc Studio, Filmustage and Scriptation: authoring/navigation, FDX handoff, branch/merge, breakdown propagation, production revisions/annotations/sides and offline use.

Acceptance: documented workflow matrix has observable criteria, fixture, automation/manual protocol, evidence and owner; regressions are release blocking; results state parity/gap truthfully rather than asserting unsupported equivalence.

### Milestone C — Script intelligence and creator control

#### MM-017 Context builder and rights-controlled retrieval

Build token/model-independent context assembly over current revisions, ProjectMemory, permitted references, CreativeIntentIR and typed states with citations, freshness checks, redaction and prompt-injection boundaries.

Acceptance: context never mixes tenants/branches or stale canon; each segment retains source IDs/rights; budget tests and adversarial retrieval tests pass.

#### MM-018 Screenplay compiler and FilmIR extraction

Compile deterministic syntax from the document kernel, then route bounded probabilistic extraction through the ModelRouter into epistemically typed candidate claims; resolve entities and create versioned FilmIR projections without promoting interpretations to authored fact.

Acceptance: the model router predates and owns every AI call; invalid structured output repairs/fails safely; reprocessing is idempotent; fixture precision/recall thresholds and provenance requirements pass.

#### MM-019 Character knowledge and deterministic state engine

Extract candidate state transitions and deterministically reduce character knowledge, suspicion/confirmation, beliefs, beliefs about what another character knows, misunderstandings, relationships, objectives, possessions, injuries, wardrobe, location, secrets, allegiance and world state by scene.

Acceptance: temporal queries are deterministic; contradictions point to evidence; human corrections persist as higher-authority claims; regression corpus meets declared thresholds.

#### MM-020 CreativeIntentIR and creator invariants

Provide film/sequence/scene/beat workflows for intended audience experience, information strategy, theme, tone, POV, character/plot invariants, visual/performance rules, exceptions, anti-rules, evolving intent, source role, confidence, lock and ownership.

Acceptance: intent is explicitly creator-owned/versioned; direct manipulation and chat write the same typed intent commands; AI suggestions distinguish stated versus inferred intent; branch/merge and stale propagation work.

#### MM-021 Proposal/ChangeSet and impact review engine

Make every AI or collaboration-driven canonical edit an inspectable Proposal against a base revision with typed patch, rationale summary, alternatives, evidence, semantic/continuity/production impact and accept/reject/modify/supersede lifecycle.

Acceptance: AI cannot directly write canon; partial acceptance is explicit; stale proposals rebase/revalidate or conflict; accepted changes atomically create a revision, audit event and invalidations.

#### MM-022 Creative Divergence / writer-unblock workflow

Generate multiple structurally distinct routes (behavioral, power inversion, silence, misdirection, visual, structural, production-constrained, radical/delete) while honoring declared invariants and rejected ideas.

Acceptance: routes are non-canonical proposal branches, explain preservation/changes and avoid hidden-authority language; explicit Executor mode is required for prose generation; the writer can combine/edit/reject; retained-suggestion/post-accept-edit metrics are captured with consent; usefulness feedback does not silently train on content.

#### MM-023 Reference Lens

Retrieve licensed, public-domain, user-owned and permitted project references; explain similarity, relevant passage/structure, difference, counter-reference, rights and why surfaced.

Acceptance: no “model training memory” claims; rights denial/redaction works; citations resolve; user can disable the lens and delete local reference indexes.

#### MM-024 Continuity and material production-impact analysis

Detect meaningful contradictions and downstream creative/continuity/production consequences using FilmIR/state/dependency data and mode-sensitive materiality thresholds.

Acceptance: high-severity fixture defects are caught at declared recall; false-positive budget is measured; author mode does not flood low-materiality logistics; findings link to evidence and can be resolved/suppressed with audit.

### Milestone D — Project memory and collaboration

#### MM-025 Project Memory and reviewed capture

Implement typed ideas, decisions, questions, research, assignments, rejected ideas, facts and links with provenance, status, search, branch/revision scope, conflict handling and promotion rules.

Acceptance: candidate memory never becomes canon automatically; rejected ideas remain retrievable but do not contaminate active context; edits preserve provenance.

#### MM-026 Single/multi-writer Room Mode

Implement lightweight physical-room UX, timers, shared boards, idea/decision capture, proposals, voting/acknowledgement, roles, Room Harvest review and writer/research-team modes.

Acceptance: a solo writer can simulate a structured room without fake participants being presented as humans; multiple writers preserve attribution/ACL; harvest requires explicit review.

#### MM-027 Live collaboration and sync

Implement presence, comments, typed collaborative operations, offline/online convergence, branch-aware sharing, conflict UI, reconnect, and audit across Web/desktop/mobile. A CRDT may manage authored document/comments/cursors/presence but cannot mutate FilmIR, intent, production or financial state outside validated domain commands/events.

Acceptance: concurrency/property/partition tests converge without silent loss; presence is ephemeral while decisions are durable; unauthorized/stale operations fail closed.

#### MM-028 Meeting capture and transcript intelligence

Implement consent-first recording/import, speaker-aware transcript correction, timestamps, searchable media links, candidate extraction and Room Harvest using the generic artifact subsystem.

Acceptance: recording consent/state is visible; transcript/candidate provenance survives edits; deletion/retention works; no candidate auto-promotes.

#### MM-029 Zoom and Google Meet adapters

Implement replaceable OAuth/webhook/import adapters with least scopes, signed callback validation, replay protection, consent UX and deterministic contract tests.

Acceptance: sandbox/live smoke evidence for configured adapters; expired/revoked token and duplicate webhook tests; mocks do not satisfy final live gates designated required.

#### MM-030 Beat frameworks and completion tracking

Implement configurable beat systems including Save the Cat and Hero's Journey as licensed/permitted templates, mapping to scenes/story functions, completion confidence, overrides, custom frameworks and accessible color themes.

Acceptance: frameworks are guidance, not prescriptive truth; manual override wins; no copyrighted template text is used without rights; changes invalidate dependent analysis.

### Milestone E — Director and visual development

#### MM-031 Director Mode, DirectorVisionGraph, and ShotIR

Implement shot identity, deterministic SceneSpace/location geometry, blocking, subject positions, camera position/height/orientation/sensor/lens and movement, composition, eyelines, light direction, color/performance intent, continuity, coverage, locked attributes, semantic annotation anchors and producer constraints.

Acceptance: ShotIR remains model/provider independent; deterministic diagrammatic/shot-card mode works with generation disabled; revisions and role-specific annotations are auditable and transfer semantically across pages; scene/intent changes mark affected shots stale.

#### MM-032 Storyboard generation and annotation

Use the ModelRouter and generic artifacts to render ShotIR storyboards with style/character/location continuity, exact prompt/input provenance, regenerate/compare, annotations and rights/safety policy.

Acceptance: storyboard is linked to shot/source revisions; locked-attribute and controlled-edit tests detect unintended drift; accepted assets are reused; regeneration-to-acceptance and correction burden are measured; stale labeling works; director/producer/writer annotations remain distinct; real configured image-provider smoke test passes.

#### MM-033 Visual Language and Color Intelligence

Model palettes, contrast, saturation, temperature, source motivation, lighting ratios, production design, wardrobe, skin-tone rendering, lens/render interaction, composition and temporal progression with rules/exceptions/anti-rules/evolution.

Acceptance: references are permitted/cited; correlation is not claimed as causation; accessibility and skin-tone safety review; choices feed ShotIR as editable proposals.

#### MM-034 Video previs provider workflow

Render selected ShotIR/storyboard sequences through Veo or a replaceable video provider, including preflight cost range and actual cost, consent gate, queued progress, caching/reuse, cancellation, provenance, continuity limitations, version comparison, timeline/animatic assembly and intended-effect review.

Acceptance: provider failure/retry is durable and idempotent; generated video is never canon by itself; real sandbox/live smoke required for final; output is labeled previs, not the finished film.

### Milestone F — Production planning and handoff

#### MM-035 Production breakdown

Derive and review cast, extras, locations, props, wardrobe, makeup, vehicles, animals, stunts, intimacy, minors, VFX/SFX, sound, equipment, permits, safety and timing from locked source revisions.

Acceptance: each element links to screenplay evidence and human verification; edits create ChangeSets; breakdown completeness/accuracy fixture thresholds pass; staleness propagates.

#### MM-036 Department handoffs, ChangeSets, and production correspondence

Provide role-filtered department views, craft-owner confirm/correct/add-assumption/ask-director/N-A actions, acknowledgements, change notices, exports, assignments, generic email/message artifact drafts, approval, delivery records and integration hooks. Confirmed department decisions return through ProjectEvents into canonical operational state.

Acceptance: no message sends without explicit authorized action; recipients/content are previewed; departments see permitted data only; screenplay changes generate auditable targeted notices.

#### MM-037 Scheduling and constraint engine

Implement strips/boards, scene durations, cast/location/resource availability, day/night, company moves, labor/rest/safety constraints, pinned decisions, scenarios, manual edits and explanation of infeasibility.

Acceptance: deterministic seeded schedules; hard constraints never silently break; alternatives and conflicts are explainable; breakdown changes invalidate affected schedules.

#### MM-038 Budget Evidence Ledger

Implement chart of accounts, quantities/rates/units, fringes, assumptions, source/date/territory/currency, incentives, contingencies, schedule-derived costs, scenarios, sensitivity, overrides, actuals/commitments and audit. Encode maturity stages: concept, script/breakdown, preliminary production, department planning, bid-backed and production forecast-to-complete.

Acceptance: every amount is formula-backed or explicitly estimated with evidence; totals reconcile; currency/rounding/property tests pass; schedule precedes budget; interval coverage/error/bias is measured by maturity, department, geography and budget class; no false “extremely accurate” claim without validation.

#### MM-039 Insurance readiness package

Generate reviewed risk/exposure inventory, schedule/budget/cast/location/stunt evidence, missing-information checklist, disclosures, document package and broker/insurer specialist handoff using generic artifacts.

Acceptance: budget and schedule are inputs; stale inputs block current labeling; output prominently states readiness support—not underwriting, binding or coverage; sensitive access and delivery are audited; a configured broker/carrier sandbox handoff or approved equivalent specialist workflow is evidenced.

### Milestone G — Audience, evaluation, and commercial artifacts

#### MM-040 Audience Resonance Lab

Implement clearly separated evidence tiers: synthetic LLM hypotheses, expert/readers, table reads/recruited panels, previs screenings, and released-outcome data. Support demographic/segment hypotheses, prompt perturbation, variance, calibration and intended-effect comparison.

Acceptance: synthetic samples are never described as human/bootstrap population samples; uncertainty and non-independence are visible; human data requires consent/provenance; repeatability and perturbation tests pass.

#### MM-041 Rubric and scene/script analysis

Implement configurable, evidence-linked rubrics for clarity, character, pacing, theme, emotion, producibility and intended effect, with multiple raters/models, disagreement, confidence, counter-evidence and creator overrides.

Acceptance: no unexplained scalar score; score changes trace to inputs/model/rubric version; adversarial and calibration tests pass; analysis is labeled advisory.

#### MM-042 Commercial scenario forecasting

Implement comparables selection/rationale, P10/P50/P90 scenarios, distribution/marketing/release/territory/talent/platform assumptions, data dates, OOD warnings, backtesting and sensitivity—not a single guaranteed number.

Acceptance: no leakage in backtests; time-split evaluation and baseline comparisons; every number links to data/method/assumptions; poor coverage or OOD fails to “insufficient evidence.”

#### MM-043 Investor deck and evidence-backed generated artifacts

Generate editable decks, one-pagers and data rooms from reviewed generic artifacts, budget and commercial scenarios with citations, data dates, disclaimers, rights and version locking.

Acceptance: every claim/number traces to current evidence; stale or unsupported claims block approved export; rendering works; creator must approve before delivery; no fabricated credentials, attachments or recipients.

### Milestone H — Integrations, platforms, and release

#### MM-044 Public API, webhooks, MCP, and interoperability

Expose an Integration Mesh with versioned least-privilege APIs and MCP tools for projects, revisions, proposals, approved artifacts and status; signed webhooks, idempotency, scopes, rate limits, audit, OpenAPI/JSON schemas, adapter SDK, capability registry, sync ledger, OAuth/secret-vault integration, per-field source-of-truth policy and SDK/examples. Include at least one real specialist production/review connector plus open-file fallback.

Acceptance: contract/negative/authorization/prompt-injection tests; tools distinguish read/propose/commit; integrations cannot bypass creator approval or ACL; backward-compatibility policy is tested.

#### MM-045 Web, macOS, Windows, iPhone, and Android applications

Deliver job-appropriate platform applications around shared domain contracts with responsive/accessibility UX, secure local persistence, offline authoring/capture, auth/subscription outage continuity, sync, deep links, update strategy, crash recovery and platform smoke suites. Maintain a dated parity matrix: Web/macOS/Windows emphasize professional authoring; iPhone/Android emphasize Room/capture/approvals/references/cards/fast semantic annotations/light edits before full long-form parity.

Acceptance: same golden project opens and retains revision/layout identity on all five platforms; offline edits recover/sync; on-set annotation/capture meets declared seconds-level latency and large-target accessibility; limitations are explicit; no platform is a static mock; platform-native security/storage expectations pass.

#### MM-046 Security, privacy, observability, evaluation, and operations

Complete threat model, data classification, tenant/ACL penetration tests, encryption/key handling, deletion/export/retention, visible no-training defaults, provider-retention/no-cross-user-cache policy, consent, opt-in training policy, egress/prompt-injection defenses, SBOM/dependency scanning, backup/restore, SLOs, structured traces/metrics without content leakage, MovieMuse Bench/model/fine-tune evaluation registry, correction-burden and Creator Leverage metrics, cost controls and incident runbooks. Preserve extension points for BYOK/customer keys/private routes/residency.

Acceptance: high/critical findings resolved; privacy workflows verified; telemetry redaction tested; local/fine-tuned routes meet declared quality/safety baselines; backup restore and incident drill reproduced independently.

#### MM-047 Golden-path E2E, independent verification, and release gate

Implement the clean-environment orchestration script and independently reproduce the complete project journey. Verify manifest/schema/DAG consistency, stale closure, all layers, all platforms and required external provider gates.

Acceptance: all 46 dependencies PASS at the current relevant state; clean checkout runs `./scripts/verify_all.sh`; no required suite is skipped; only success prints exactly `MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS` as its final line and exits 0.

## 4. Forty-one-step golden demo and E2E journey

All steps use one project and preserve identity/provenance across platforms:

1. Create an account/local profile and project.
2. Set creator ownership, collaborators, roles and sensitive-data permissions.
3. Import the golden FDX and review its loss report.
4. Confirm deterministic pagination and production metadata.
5. Work offline and through simulated auth/subscription/AI outage: edit, save, close and reopen.
6. Create a checkpoint and alternate branch.
7. Make concurrent CRDT-backed authored edits on two clients, resolve a merge, and prove CRDT state cannot bypass FilmIR commands.
8. Export FDX and execute the compatibility round trip.
9. Compile ScreenplayAST and FilmIR.
10. Review/correct entity resolution and evidence.
11. Inspect a character's knowledge/state at two scenes.
12. Record CreativeIntentIR and creative invariants.
13. Enable Reference Lens and inspect rights/citations/counter-reference.
14. Request writer-unblock alternatives.
15. Compare rationale, impacts and evidence.
16. Modify and accept one Proposal; reject another.
17. Confirm immutable revision, audit and dependent staleness.
18. Run continuity/material-impact analysis.
19. Add beats and a custom beat framework override.
20. Start a solo Room Mode session and capture candidates.
21. Run a multi-writer collaboration with attribution/comments.
22. Import/capture a consented meeting transcript.
23. Correct a speaker and perform Room Harvest review.
24. Exercise configured Zoom/Meet sandbox/live adapter.
25. Promote a reviewed decision to Project Memory without silently changing script canon.
26. Open Director Mode and author deterministic SceneSpace, ShotIR, locked attributes and semantic annotations.
27. Define visual/color rules, an exception and an anti-rule.
28. Generate/compare annotated storyboard versions.
29. Generate a short video previs and record intended-effect review.
30. Generate and human-review production breakdown.
31. Send an approved department ChangeSet/notice through a test delivery channel.
32. Create and constrain two schedule scenarios.
33. Generate a budget with evidence, assumptions and sensitivity.
34. Generate insurance-readiness package from current schedule/budget and complete the configured specialist sandbox handoff.
35. Run synthetic audience hypotheses with proper evidence-tier labeling.
36. Add a consented human/expert response and compare calibration.
37. Run rubric analysis with disagreement/counter-evidence.
38. Generate commercial P10/P50/P90 scenarios and OOD behavior.
39. Generate, review and export an evidence-backed investor deck.
40. Read/propose through API/MCP, exercise the specialist connector/source-of-truth policy, and prove neither can bypass approval.
41. Open the same project on Web, macOS, Windows, iPhone and Android; verify document/revision/layout identity, then pass the final clean gate.

## 5. Product-validation and PMF gates

Research artifacts are inputs, not proof of demand. Validate the wedge with real work rather than “would you use AI?” surveys:

- Recruit working screenwriters/writer-directors, directors/DPs, AD/production-management professionals, and department heads/script supervisors using consented real scenes and revisions.
- Run an authoring switch/sidecar test; measure whether users voluntarily return to Movie Muse as primary editor or prefer it beside Final Draft/Arc.
- Test Divergence Engine against the creator's normal process using time-to-next-authored-progress, regret/rework, retained suggestion rate and post-accept edit distance.
- Test Room Harvest acceptance/correction time and whether capture disrupts or chills discussion.
- Test continuity and breakdown recall together with false-critical-alert rate and correction minutes.
- Test ShotIR/SceneSpace controlled edits against regeneration-heavy visual workflows.
- Calibrate budget intervals by information maturity and Audience Lab hypotheses against separately consented human evidence.

Stage advancement requires retained behavior and a positive Creator Leverage Ratio, not favorable survey language alone. Every study records cohort, recruitment, protocol, consent, source artifact, baseline, success threshold, falsification condition, limitations and decision. A failed product gate narrows or resequences release; it does not permit falsifying the 47-package implementation ledger.

## 6. Competitive regression matrix

The goal is workflow confidence, not copying proprietary UI or claiming blanket parity.

| Benchmark | Required Movie Muse regression | Evidence |
|---|---|---|
| Final Draft | keyboard authoring; FDX import/export; pagination; locked pages/scenes; revisions/colors/marks; A/B and omitted material | automated corpus plus licensed/manual round-trip report |
| Celtx | script-to-breakdown/catalog/schedule/budget linkage and team handoff | seeded project flow, propagation and export evidence |
| Arc Studio | outline/cards, history, collaboration, branch alternative and merge | multi-client E2E with conflict and attribution evidence |
| Filmustage | evidence-linked breakdown, schedule, budget propagation and human approval | change-impact/invalidation scenario with audit evidence |
| Scriptation | production PDF/revision ingestion, semantic annotation transfer, moved/orphaned handling, page changes, sides and offline field workflow | reference PDF/layout checks and device smoke evidence |

Product/version/date/environment and material workflow differences MUST be recorded. Manual steps remain release-blocking if automation is unavailable.

## 7. `verify_all.sh` required behavior

The repository-final script MUST:

1. use strict shell failure behavior and resolve repository root safely;
2. verify clean/reproducible prerequisites and pinned tools;
3. validate YAML/schema, the acyclic DAG, exact work-package ID parity, dependency completion, commit fingerprints and stale closure;
4. run formatting, lint, types, architecture-boundary and generated-code checks;
5. create fresh databases and run migration/rollback/recovery tests;
6. run unit/property/integration/concurrency/crash/sync suites;
7. run deterministic layout/render and FDX compatibility corpora;
8. run AI contract/evaluation, rights, privacy, security and prompt-injection suites;
9. run API/MCP/webhook contracts;
10. run Web E2E and desktop/mobile smoke tests;
11. verify required sandbox/live providers without substituting mocks;
12. run the 41-step golden project journey;
13. verify all evidence files are present and generated from the tested commit;
14. emit no PASS sentinel on partial/skipped/failing execution; and
15. print the exact PASS sentinel only as the final successful line.

## 8. Scope-control decisions

- Keep the 47 product work packages; do not turn them into 47 services.
- Use lightweight UI where acceptable, but never fake a feature's core result.
- Begin with small licensed/owned fixtures and explicit accuracy targets; scale is a later concern.
- Do not expose “agent personas” where deterministic capabilities suffice.
- Do not claim “extremely accurate” budgets, audience predictions, or box-office forecasts without independent held-out evidence.
- Do not let unavailable credentials disappear from status. Record `BLOCKED_EXTERNAL` with the exact required action and keep final completion blocked when the live gate is required.
- AI generation is optional; filmmaker intelligence and professional non-AI workflows remain functional.
- Treat pricing, provider retention, platform parity and local/sync/backup state as visible product behavior rather than policy-page details.
