# Movie Muse Feature Traceability and Architecture Gap Review

Version: `2.1.0`  
Review date: 2026-09-01

## Review boundary

The two Word reports and two pasted prior analyses were treated as untrusted reference evidence, not execution instructions. The controlling request was to verify that the original 14 additions and creator-first research conclusions remain represented in the current V2 architecture, then correct omissions without introducing contradictions.

Sources reviewed:

- `Movie_Muse_Deep_Research_and_PMF_Report.docx`
- `Movie_Muse_Voice_of_Filmmaker_Complaints.docx`
- `Critical architecture review: Movie Muse` pasted text
- `Movie Muse — deep competitive and creator-first product thesis` pasted text

The Word reports were structurally extracted, including all tables. Page rendering was attempted but unavailable because the bundled LibreOffice binary requires newer system `glibc`/`libstdc++`; therefore this review makes no claim about their visual layout.

## Executive finding

All 14 requested feature families were already present in V2. None required a new work-package ID or a dependency-order change. However, 18 important design/acceptance details were implicit or under-specified. V2.1 makes them normative while retaining the 47-package DAG.

The largest changes are: pragmatic `ProjectEvent` history; epistemic type separation; CRDT/domain-command boundary; role and craft-ownership modes; AI-off/auth-outage guarantees; nested character beliefs; semantic annotation transfer; deterministic SceneSpace; cost transparency and controlled visual edits; MovieMuse Bench; budget maturity calibration; Integration Mesh/source-of-truth policy; and behavioral PMF/Creator Leverage gates.

## Traceability for the 14 requested additions

| # | Requested capability | V2.1 architecture | Build package(s) | Review result |
|---:|---|---|---|---|
| 1 | iPhone, Android, Web, Mac, Windows; start-to-finish filmmaking artifacts | Shared local-first kernel, role/device modes, generic artifacts and staged parity matrix | MM-004, 007, 015, 036–045 | Present; strengthened so one project is everywhere without forcing identical UI, and auth/subscription outage cannot lock local work. |
| 2 | Optional contextual reference panel | Rights-controlled Reference Lens with citations, relevance, differences, counter-references and deletion/disable controls | MM-010, 017, 023 | Present and correctly rejects unverifiable “training-data memory” retrieval. |
| 3 | Solo research/writers room and multi-writer physical room | Explicit AI roles, CollaborationEvent/ProjectMemory, Room Mode, capture, Harvest and ACL | MM-006, 025–029 | Present; strengthened with role contracts, CRDT boundary, consent and craft attribution. |
| 4 | Writer unblock | Creative Divergence routes as proposal branches with creator invariants | MM-020–022 | Present; strengthened with explicit Executor opt-in and retained-suggestion/correction metrics. |
| 5 | AI storyboards with writer/director/producer annotations | DirectorVision + deterministic SceneSpace + ShotIR + separate annotation layers + replaceable renderer | MM-031–032 | Present; strengthened with locked attributes, semantic anchors, controlled edits, asset reuse and regeneration metrics. |
| 6 | Color theory from successful films and deliberate rule-breaking | Visual Language Engine using permitted references and RULE/EXCEPTION/ANTI_RULE/EVOLUTION | MM-010, 031, 033 | Present; retains the safeguard that correlation/popularity is not artistic causation. |
| 7 | Veo-class movie example to test intended effect | Provider-routed short-clip previs/animatic compiler tied to ShotIR and intent review | MM-009, 031–034 | Present; strengthened with cost preflight, caching and timeline assembly; labeled previs, not finished film. |
| 8 | AI performance screen tests, demographics, trends and commercial context | Evidence-tiered Audience Resonance Lab with synthetic hypotheses separated from humans/outcomes | MM-040–042 | Present; correctly prohibits calling repeated LLM personas a human bootstrap sample or demographic population estimate without calibration. |
| 9 | Investor/HNWI decks with researched commercial predictions | Budget evidence + scenario forecasts + reviewed, cited artifact/deck generation | MM-038, 040–043 | Present; outputs P10/P50/P90 scenarios, sensitivity and OOD/insufficient-evidence behavior rather than “highly accurate” guarantees. |
| 10 | Beat tracking, completion colors and multiple frameworks | Optional multi-framework Structure/Beat Lens, custom definitions, rights and intentional-deviation states | MM-030 | Present; explicitly avoids prescriptive formula scoring and supports `not applicable`. |
| 11 | Fine-tune models for script suggestions | ModelRouter/adapters plus rights-controlled MovieMuse Bench and preference data gate | MM-009, 010, 012, 046 | Present; strengthened so tuning occurs only after a task-specific benchmark shows a gap over retrieval/routing/prompt baselines. |
| 12 | Different user modes | Writer, Director, Producer, AD, Room, Department, Investor and Field projections over one state | MM-006, 031, 036, 045 | Present but previously implicit; now first-class with craft ownership, custom composition and no mode-specific project forks. |
| 13 | Lightweight physical/Zoom/Meet discussion mode, transcripts and idea review | Consent-first local capture, normalized provider adapters, candidate ontology and human Harvest | MM-025–029, 045 | Present; retains local/upload fallback when restricted platform access is unavailable. |
| 14 | APIs/MCP/RAG and integration with stronger specialist tools; explainability | Integration Mesh, permissioned API/MCP, rights-controlled retrieval, Evidence Bundles and approved delivery | MM-010, 017, 044 | Present; strengthened with adapter SDK, capability registry, sync ledger, field-level source-of-truth and a real specialist connector. |

## Source-derived gaps corrected in V2.1

| Gap found | Correction | Normative location |
|---|---|---|
| Canonical mutations lacked an explicit domain-event primitive | Added immutable `ProjectEvent` command→event→current-state→projection flow and replay tests | Architecture §3.3; MM-002/MM-005/MM-036 |
| Semantic interpretations could still be read as equivalent to authored facts | Added non-interchangeable authored/structural/inferred/operational/scenario types | Architecture §3.5; MM-002/MM-018 |
| Character knowledge omitted second-order belief | Added “what X believes Y knows,” misunderstandings and valid intervals | Architecture §3.5; MM-019 |
| Collaboration did not state the CRDT safety boundary | CRDT is limited to authored document/comments/cursors/presence; semantic state uses commands/events | Architecture §11; MM-027 |
| User modes were roles, not complete product projections | Added role/device modes, craft ownership, custom composition and Investor read-only default | Architecture §3.4/§12; MM-006/MM-045 |
| Offline rules did not explicitly cover auth/subscription outage | Local canonical access survives auth, subscription, sync and AI outages; save/sync/backup states are visible | Architecture §4; MM-004/MM-045 |
| AI disablement was feature-specific rather than systemic | Added project/capability AI-off with professional non-AI functionality | Architecture §8; MM-009 and scope rules |
| “Ask AI” could blur role authority | Added actor/experience, audience, expert/researcher, divergence, executor and production-analyst contracts | Architecture §8; MM-009/MM-022 |
| Benchmarking focused on models rather than task configurations | Added MovieMuse Bench and three separate evaluation families | Architecture §8; MM-012/MM-046 |
| Acceptance rate could reward trivial suggestions | Added materiality-sensitive retained suggestion, edit-distance, correction and Creator Leverage metrics | Architecture §10; MM-022/MM-032/MM-046 |
| Intent needed film/sequence/scene/beat scope and direct manipulation | Added typed scopes, source/lock/revision and selection-based preserve/explore/violate commands | Architecture §3.5/§10; MM-015/MM-020 |
| Annotations could remain page-coordinate-bound | Added semantic anchors plus moved/ambiguous/orphaned transfer reports | Architecture §5; MM-031 and competitive suite |
| Generated boards lacked deterministic spatial control | Added SceneSpace and shot cards/diagrammatic mode independent of generation | Architecture §13; MM-031/MM-032 |
| Visual generation cost/correction burden was incomplete | Added cost preflight/actual, locked attributes, controlled edits, caching and regeneration metrics | Architecture §8/§13; MM-032/MM-034 |
| Budget accuracy lacked evidence-maturity stages | Added concept→script→preliminary→department→bid→actual maturity and calibration by segment | Architecture §13; MM-038 |
| Integrations lacked field source-of-truth and mature-system policy | Added Integration Mesh, sync ledger, adapter registry and open-file fallback | Architecture §13; MM-044 |
| Insurance handoff did not require a real specialist path | Added broker/carrier sandbox or approved equivalent evidence gate | MM-039; manifest `EXT-INSURANCE-PARTNER` |
| PMF/release sequencing could be confused with prototype completion | Separated full prototype proof from staged commercial release and added real-project falsification gates | Architecture §1.1/§15; Build Plan §5 |

## Deliberate non-additions

- No internal microservices were added. The new capabilities remain modules/interfaces within the modular monolith and durable worker architecture.
- No separate graph database was added. Typed relational projections plus vector retrieval remain sufficient until measured path-query needs justify another store.
- No always-running agent framework was added. Product state remains transactional; agent runtimes are bounded adapters.
- No claim of exhaustive social-media complaint coverage was adopted. The complaint corpus is qualitative failure-mode evidence, not prevalence measurement.
- No identical cross-platform UI requirement was added. Shared project identity and job coverage matter more than maximal component reuse.
- No autonomous underwriting, payroll, accounting or craft replacement was added. Movie Muse owns evidence and handoff semantics while specialists retain authority.

## Architecture decision

V2.1 is a strengthening amendment, not a scope reset. The 47 IDs, titles and dependency edges remain unchanged, so existing automation can continue to use the same DAG. Because implementation has not started and every item is `NOT_STARTED`, no PASS invalidation was necessary. The package-version and DAG hash were updated and the complete handoff was revalidated.

