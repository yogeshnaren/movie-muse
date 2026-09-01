# Movie Muse V2 Architecture Amendment and Normative Specification

Version: `2.1.0`  
Normative language: MUST, MUST NOT, SHOULD, MAY have their usual requirements meaning.

## 1. Product boundary

Movie Muse is a creator-controlled, professional filmmaking workspace spanning screenplay authoring, story intelligence, collaboration, visualization, production planning, audience hypotheses, commercial scenarios, and evidence-backed artifacts on Web, macOS, Windows, iPhone, and Android.

Its first principle is not “AI writes a movie.” It is:

> Movie Muse understands how meaningful creative and production decisions relate, while the creator controls what becomes canon.

AI output MUST enter as a `Proposal`, `CandidateClaim`, or `GeneratedArtifactVersion`. It MUST NOT mutate canonical screenplay, project memory, schedule, budget, or production state without an authorized acceptance transaction.

### 1.1 Prototype breadth versus product release sequencing

The working prototype retains all 47 required feature packages so the complete architecture can be proven. That does not mean all surfaces launch commercially at once. Release sequencing is evidence-gated:

1. Creator wedge: professional revision, FDX, FilmIR/CreativeIntentIR, character knowledge, continuity, proposals, Reference Lens, divergence, project memory and collaboration.
2. Room/director expansion: multi-writer rooms, meeting capture, DirectorVision/ShotIR, controllable storyboards and integration substrate.
3. Production translation: breakdown, department contracts, scheduling, budget evidence and specialist handoffs.
4. Research-gated intelligence: video previs, calibrated audience hypotheses, commercial scenarios and investor artifacts.

Advancement MUST depend on real-project evidence, not feature completion alone. The initial ICP hypothesis is writer-directors/filmmaker-producers and small creator-led teams. Movie Muse MUST remain usable as an interoperable sidecar if switching tests show that users retain Final Draft or Arc as their canonical editor.

## 2. Architecture shape

V2 is a modular monolith with durable workers:

```text
Web / Desktop / Mobile clients
        |
Application API + local application service
        |
Modular monolith
  document | revisions | ACL | artifacts | AI orchestration
  film IR  | collaboration | visual | production | intelligence
        |
Transactional database + blob store + outbox
        |
Durable worker processes
        |
Model providers / media providers / meeting adapters / exports
```

Module boundaries MUST be enforced in code and tests. Cross-module calls use typed application interfaces and domain events. Modules MUST NOT reach into another module's tables or internal classes. The monolith and worker MAY be deployed as separate processes, but they share one versioned domain contract.

Internal microservices are out of scope unless an architecture decision record demonstrates at least one of: independently measured scaling pressure, a security/isolation boundary, a distinct availability target, or a team/deployment boundary whose benefit exceeds distributed-system cost.

Product workflow state lives in the database. An agent framework MAY execute bounded reasoning, but MUST NOT be the source of truth or hold an indefinitely suspended approval workflow.

Core primitives are distinguished from replaceable features. A capability belongs in the durable core when it creates persistent project knowledge, affects multiple workflows, participates in invalidation, is inspectable/correctable, survives model replacement, and creates permitted evaluation evidence. Renderers and provider calls remain replaceable capability adapters.

## 3. Canonical domain model

### 3.1 Professional document kernel

`ScreenplayDocument` is a typed, versioned tree—not arbitrary rich text. Minimum block types:

`SceneHeading`, `Action`, `Character`, `Parenthetical`, `Dialogue`, `Transition`, `Shot`, `General`, `Lyrics`, `PageBreak`, `TitlePageElement`.

The kernel MUST preserve stable IDs for document, sequence, block, inline span, scene, character cue, dialogue pair, note, revision mark, production tag, and attachment. Editor-framework nodes are projections/adapters; they are not persistence contracts.

The kernel MUST support dual dialogue, forced elements, continued dialogue, extensions, title pages, notes, boneyard/omitted material, Unicode, custom paper sizes, configurable screenplay styles, scene numbers including alphanumeric variants, and lossless unknown-extension preservation where safe.

### 3.2 Immutable history

- `Revision`: immutable content-addressed document/project state with parent revision IDs, author, timestamp, ChangeSet, schema version, and integrity hash.
- `Branch`: named movable reference to one revision plus protected/archived state; branch movement is atomic and audited.
- `Checkpoint`: immutable named reference to a revision, never silently moved.
- `ChangeSet`: ordered typed operations against an explicit base revision.
- `Merge`: auditable three-way merge with base, source, target, conflicts, resolutions, author, and resulting revision.
- `Proposal`: immutable candidate ChangeSet against `base_revision_id`, with intent, rationale summary, semantic/continuity/production impacts, provenance, status, and revalidation record.

Canon is the head revision of the selected canonical branch. Rejected or superseded proposals remain searchable. If a proposal base differs from branch head, acceptance MUST fail closed until deterministic rebase/revalidation succeeds or a human resolves conflicts.

### 3.3 Canonical domain-event history

Every accepted canonical mutation emits an immutable `ProjectEvent`, such as `ScreenplayPatchAccepted`, `CharacterIntentLocked`, `SceneMoved`, `ProductionRequirementConfirmed`, `DepartmentDecisionConfirmed`, or `AssumptionChanged`. Commands produce events; event handlers update ordinary transactional current-state tables and derived projections. This is pragmatic event history, not a requirement for doctrinaire event sourcing.

Events carry project, branch, base/result revision, actor/effective principal, command/operation ID, schema version, causal/correlation IDs and integrity hash. Replay/reconstruction, audit, undo-via-new-command, invalidation and debugging are tested. Event/preference data MUST NOT become training data without separate rights and opt-in consent.

### 3.4 First-class ACL and craft ownership

ACL evaluation covers organization, project, document, branch, artifact, and operation. Minimum roles: owner, administrator, writer, director, producer, department contributor, reviewer, viewer, integration service. Permissions distinguish read, comment, propose, accept, merge, export, manage production locks, manage ACL, run paid/provider operations, and view sensitive financial/rights data.

Authorization MUST run server-side/local-authority-side for every command and again in durable workers. Cached permissions MUST be versioned and invalidated on membership/ACL changes. Branch protection and merge approval are domain rules, not UI conventions. Audit records are append-only and include actor, effective principal, operation, object, before/after revision IDs, policy decision, time, and correlation ID.

Craft ownership is encoded in policy: writers own authored story choices; Director/DP own visual language and coverage according to project policy; Costume, Art, VFX/SFX, AD and other departments confirm decisions in their domains; producers control authorized financial/operational approvals. AI can propose and calculate but cannot impersonate a craft owner's confirmation.

### 3.5 Film model and epistemic levels

The Film Graph is a versioned family of typed projections:

1. `ScreenplayAST`: deterministic syntax.
2. `FilmIR`: normalized entities, scenes, events, mentions, chronology, locations, props, cast and explicit facts.
3. `SemanticClaims`: probabilistic objectives, conflict, emotion, themes, relationships, and knowledge transitions with confidence and provenance.
4. `CreativeIntentIR`: creator-stated intended audience experience, invariants, themes, tone, visual/performance rules, exceptions and anti-rules.
5. `OperationalProjections`: continuity, breakdown, schedule constraints, resources, budget evidence, insurance-readiness inputs.
6. `ScenarioModels`: audience hypotheses and commercial scenarios with assumptions and calibration state.

Probabilistic extraction creates claims; deterministic reducers compute character knowledge, possessions, injury, relationship, wardrobe, location, secret, objective, and world state over scene order.

Authored facts, structural facts, inferred semantic claims, operational assumptions and scenario outputs MUST have distinct types and cannot be promoted implicitly. Character epistemic state includes what a character knows/suspects/believes, what one character believes another character knows, and confidence/source/valid scene interval. Creator intent is scoped at film, sequence, scene and beat levels and records source role (`writer`, `director`, `cinematographer`, other authorized craft role, or `inferred`), lock state, revision and provenance.

## 4. Local-first persistence and sync

Every client capable of editing MUST persist authoritative local revisions before acknowledging save. The baseline design uses an embedded transactional database plus content-addressed local blobs. Network loss MUST NOT block open, edit, save, branch, checkpoint, diff, or local export.

Authentication, subscription, licensing, sync or AI-provider outages MUST NOT prevent an entitled user from opening and editing already-local canonical work. The UI MUST distinguish saved locally, queued for sync, synced, backed up, conflicted and recovery-only states. Long-term compatibility tests cover old local databases, backups and document versions.

Local commands append immutable revisions and an outbox record in one transaction. Sync sends idempotent envelopes containing project, branch, base revision, resulting revision/hash, actor, device, operation ID, schema version, and ACL epoch. The server deduplicates by operation ID and verifies ancestry, integrity, and authorization. Remote changes arrive through an inbox and are applied transactionally.

Concurrent changes never use silent last-writer-wins. Non-overlapping typed operations MAY merge automatically. Semantic or structural conflicts create an explicit merge record and UI resolution. Offline ACL revocation is handled by quarantining unsynced work into a local recovery branch; revoked work is never silently uploaded or destroyed.

Migrations MUST be forward-tested, rollback/recovery-tested, crash-safe, and idempotent. Encryption keys, local database, cached model context, transcripts, media, and financial information follow documented platform security storage policies.

AI extraction, indexing, backup and sync run outside the keystroke-critical path with explicit latency/resource budgets. Their failure MUST NOT corrupt or stall acknowledged local authoring.

## 5. Deterministic layout and production revisions

Layout is a pure, versioned function:

```text
LayoutResult = layout(document_revision, style_profile,
                      paper_profile, font_metrics_version,
                      production_lock_state, layout_engine_version)
```

Identical inputs MUST produce identical line breaks, page breaks, scene locations, dialogue continuations, and hashes on every supported platform. Font assets/metrics are pinned. No browser-native measurement may be the canonical paginator.

Production semantics MUST include locked pages, locked scene numbers, revision sets/colors, revision marks, changed-page detection, A/B page insertion, A/B scene numbering, omitted scenes, headers/footers, MORE/CONT'D behavior, page/scene renumbering policy, production tags, sides generation, and clean/revision exports. Unlocking or repagination requires explicit permission and a recorded domain event.

Annotations, blocking notes and department decisions anchor primarily to stable semantic entities (scene/block/span/shot IDs plus resilient local anchors), never only to page coordinates. Revision transfer reports moved, ambiguous and orphaned anchors for human resolution.

Pagination verification compares structured layout traces and rendered reference output, with documented tolerances. Text, block type, scene identity, production locks, and revision semantics have zero-loss tolerance.

## 6. FDX compatibility program

FDX is a first-class compatibility boundary, not a one-time importer. The suite MUST contain legally distributable fixtures for ordinary and adversarial scripts: title pages, every paragraph type, dual dialogue, extensions, notes, tags, revisions, locked pages, omitted scenes, A/B scenes/pages, Unicode/RTL samples, custom formatting, and unknown-but-safe extension elements.

Required pathways:

- FDX → Movie Muse → FDX semantic round trip.
- Movie Muse → FDX → Final Draft → FDX → Movie Muse, where licensed automation/manual verification is available.
- Fountain/plain-text/PDF import as explicitly lossy pathways with user-visible reports.
- Production revision round trips preserving lock and revision behavior.

Acceptance is not “opens successfully.” It requires: no text or scene loss; stable ordering and element semantics; production metadata preservation; no meaningful pagination drift under the pinned compatibility profile; deterministic repeated exports; validation against the supported FDX schema/profile; unknown-data preservation or an explicit loss report; and human review in Final Draft for the release corpus.

## 7. Dependency graph and incremental build semantics

`dependency_dag.yaml` is authoritative for work-package order. Product-derived data also uses a typed dependency graph:

```text
source revision / accepted claim / configuration / model / rights record
      -> derived projection -> artifact version -> downstream artifact
```

Every derived node records input IDs/hashes, code version, schema version, model/provider version, prompt/template version, rights snapshot, and produced-at time. An accepted ChangeSet calculates the minimal invalidation frontier, marks the entire dependent closure stale, and queues recomputation. Stale data MAY remain viewable when labeled but MUST NOT be represented as current or used for a consequential export without explicit override and audit.

Build-status PASS obeys the same rule. A work package records a verification commit and input fingerprint. A relevant code, schema, fixture, configuration, dependency-lock, or verifier change invalidates it to STALE; all transitive dependents become STALE. Reverting code does not resurrect PASS automatically—verification must run again.

## 8. Durable work and model routing

Workers lease jobs from a durable queue with idempotency key, attempt count, heartbeat, timeout, retry policy, dead-letter state, cancellation, priority, cost budget, and trace ID. Side effects use transactional outbox/inbox or provider-specific idempotency. A crash between provider response and persistence MUST be recoverable without duplicate canonical mutations.

The `ModelRouter` MUST exist before any AI extractor/generator. Requests declare capability, data classification, latency/cost budget, offline requirement, context size, tool/structured-output needs, and quality tier. Policy chooses local or remote providers, records the decision, enforces consent and rights, and provides deterministic test doubles. Local-model support and fine-tuned adapters are routes, not separate product architectures. Live-provider smoke tests cannot be replaced by mocks when marked final-required.

AI is optional at project and capability level. Disabling it leaves professional authoring, local history, manual project memory, production revisions and exports functional. Paid/provider operations show an estimated cost/credit range before authorization, cache reusable accepted results, and report actual usage afterward. Core writing access MUST NOT depend on opaque generation credits.

AI roles have explicit epistemic contracts—such as actor/experience, audience, expert/researcher, divergence partner, executor and production analyst—defining whether they may interpret, retrieve, propose or calculate. “Ask AI” MUST NOT collapse these distinct authorities.

`MovieMuse Bench` evaluates task configurations (model + prompt + context strategy + tools + decoding + schema), not model brand alone. It separates objective extraction/continuity/breakdown ground truth, blinded human creative preference, and observed workflow utility. Fine-tuning begins only after a rights-controlled benchmark shows a durable gap over routing/retrieval/prompt baselines.

## 9. Generic artifact subsystem

Before specialized decks, emails, reports, schedules, budgets, storyboards, or insurance packets, implement `Artifact`, `ArtifactVersion`, `ArtifactTemplate`, `ArtifactRender`, `ArtifactLink`, and `DeliveryRecord`.

Every artifact version has immutable inputs, source revision, template/version, renderer version, evidence/rights links, creator/editor, classification, status, and checksum. Generated artifacts are drafts until reviewed. Rendering is reproducible; export/delivery is permission-checked and audited. Domain-specific artifacts extend typed metadata rather than inventing new storage/lifecycle systems.

## 10. Creator control, provenance, and explainability

Each consequential recommendation or claim exposes an `EvidenceBundle`: claim/recommendation, cited project nodes and permitted sources, method summary, model and version, assumptions, confidence/uncertainty, alternatives, counter-evidence, sensitivity where relevant, rights/license, timestamp, and human-validation state. It MUST NOT expose or claim to expose private chain-of-thought.

Materiality thresholds protect creative flow. Author mode foregrounds creative and meaningful continuity impacts while compressing logistics. Production mode may invert emphasis. Users can inspect all known consequences without being interrupted by all of them.

Contextual direct manipulation is first-class: a creator may select beats, lines, scenes, intent curves or shot attributes and declare what to preserve, explore, lock or intentionally violate. Those choices become typed intent/constraint data, not an unstructured chat-only instruction.

Product evaluation includes correction minutes, false-critical-alert rate, retained suggestion rate (accepted output that survives later revisions), post-accept edit distance, regenerations per accepted visual, and `Creator Leverage Ratio = useful cognitive/clerical work removed ÷ verification/correction/control cost introduced`. Acceptance clicks alone are insufficient.

## 11. Collaboration and capture

Room transcripts, notes, integrations, and research produce candidate records: idea, decision, question, assignment, research request, character fact, scene proposal, or rejected idea. “Room Harvest” requires review before promotion into project memory or canon. Speaker corrections and transcript edits retain provenance.

Live collaboration operates on typed document operations and immutable revisions. Presence is ephemeral; comments, decisions, proposals, merges, and acknowledgements are durable. Meeting-provider adapters are replaceable boundaries and must disclose recording/consent requirements.

A CRDT MAY coordinate authored screenplay blocks, comments, cursors and presence, including offline convergence. It MUST NOT write arbitrary FilmIR, intent, production, budget or scenario state. Canonical semantic mutations still pass through validated commands/events, ACL, proposals where applicable and dependency invalidation.

## 12. Role and device modes

Writer, Director, Producer, AD, Room, Department, Investor and Field/On-set modes are permissioned projections over one project, never separate project copies. Small teams may compose modes when one person holds several roles. Investor mode is normally read-only over explicitly approved artifact versions.

One project must be available everywhere, but identical UI parity is not required. Web/macOS/Windows prioritize professional authoring and production review. iPhone/Android initially prioritize capture, Room Mode, approvals, references, scene cards, fast semantic annotations, notifications and lightweight edits. Field interactions use large targets and seconds-level latency. A dated parity matrix makes every platform job and limitation explicit.

## 13. Visual, production, and intelligence boundaries

- `DirectorVisionGraph`, deterministic `SceneSpace` and `ShotIR` own location geometry, blocking, subject positions, camera position/height/orientation/sensor/lens/movement, composition, eyelines, light direction, color, performance intent, continuity, locked attributes and annotations. Image/video models are replaceable renderers of defined shots.
- Visual-language rules support RULE, EXCEPTION, ANTI_RULE, and EVOLUTION. Popularity correlation MUST NOT be presented as artistic causation.
- Production breakdown precedes scheduling. Scheduling precedes the budget evidence ledger. Budget maturity is explicit: concept feasibility band, script/breakdown range, preliminary production estimate, department-confirmed working budget, bid-backed estimate, and production forecast-to-complete. Accuracy/calibration is measured by maturity, department, geography and budget class. Insurance readiness consumes breakdown, schedule, and budget and hands off through a broker/carrier or specialist integration; it does not issue insurance or replace a broker/underwriter.
- Audience Resonance Lab labels LLM personas as synthetic hypotheses and separates them from expert, table-read, panel, screening, and release-outcome evidence tiers.
- Commercial outputs use scenarios (including P10/P50/P90), comparables methodology, assumptions, data dates, model version, uncertainty/OOD warnings, and sensitivity. They are never guarantees.
- The Integration Mesh provides adapter SDK, capability registry, OAuth/secret vault, idempotent webhooks, sync ledger and field-level source-of-truth policy. Mature payroll, accounting, review, insurance and production services SHOULD be integrated rather than recreated when they provide the stronger regulated/specialist workflow; open file export remains the fallback when APIs are unavailable.

## 14. Security, privacy, and rights

Data is classified at ingestion. Least privilege, tenant isolation, encryption, key rotation, redaction, deletion/export, retention, consent, prompt-injection defenses, egress policy, malware scanning, signed callbacks, rate/cost limits, and auditability are release criteria. Training on user content is opt-in only, separately consented, reversible where technically possible, and never implied by product use.

Baseline provider policy requires minimum retention/zero-data-retention where available, project-scoped retrieval, no cross-user prompt caching, and visible no-training defaults. BYOK, customer-managed keys, private/self-hosted model routes, enterprise VPC deployment and regional residency are planned extension points, not assumptions hidden from the domain model.

Reference Lens retrieves only user-owned, public-domain, licensed, or otherwise permitted sources registered in the Rights Registry. Every surfaced reference displays source and rights context.

## 15. Verification, product validation, and release contract

Tests are layered: schema/domain, property, unit, migration, integration, crash/retry, sync/concurrency, security/rights, AI contract/evaluation, deterministic layout/render, FDX compatibility, API/MCP contracts, accessibility, platform smoke, competitive regression, external-provider sandbox/live, and golden-path E2E.

An independent verifier MUST be a separate agent or person who did not implement the item and who reruns acceptance from committed instructions without private implementation context. The verifier records identity, commit, commands, environment, results, evidence paths, and limitations. Self-review is useful but does not satisfy independence.

Product validation uses real scenes/projects with screenwriters/writer-directors, directors/DPs, AD/production-management participants and department heads/script supervisors. It measures context recovery, contradiction detection, revision communication, correction burden, block duration, repeated department questions, budget uncertainty, authorship, convergence/genericness, unwanted interruption, verification fatigue and departmental trust. Stage gates record falsification criteria, including editor-versus-sidecar preference; favorable surveys without retained behavior do not establish PMF.

The final gate is a clean-checkout `./scripts/verify_all.sh`. It fails closed on missing tools, skipped required suites, stale items, unavailable required external validation, dirty generated artifacts, dependency cycles, manifest/schema mismatch, or any nonzero subcommand. Only complete success prints:

```text
MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS
```
