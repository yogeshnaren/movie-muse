# Movie Muse V2 Dependency Graph

The machine source of truth is `dependency_dag.yaml`. This file is explanatory.

V2.1 strengthened acceptance requirements without changing the 47 node IDs, titles or dependency edges.

```mermaid
flowchart TD
  R[MM-001 Repo] --> S[MM-002 Schemas]
  S --> D[MM-003 Document kernel]
  S --> L[MM-004 Local persistence]
  D --> V[MM-005 Revisions/branches/merge]
  L --> V
  V --> A[MM-006 ACL/audit]
  A --> G[MM-007 Generic artifacts]
  A --> W[MM-008 Durable worker]
  W --> M[MM-009 Model router]
  G --> P[MM-010 Rights/provenance]
  V --> X[MM-011 Dependency/invalidation]
  P --> F[MM-012 Golden fixtures]
  X --> F
  F --> I[MM-013 FDX]
  I --> Y[MM-014 Layout/production revisions]
  Y --> E[MM-015 Professional editor]
  E --> C[MM-016 Competitive regression]
  M --> K[MM-017 Context/retrieval]
  P --> K
  K --> IR[MM-018 FilmIR]
  IR --> ST[MM-019 State engine]
  ST --> CI[MM-020 CreativeIntentIR]
  CI --> PR[MM-021 Proposals]
  PR --> UB[MM-022 Writer unblock]
  PR --> RL[MM-023 Reference Lens]
  PR --> CO[MM-024 Continuity/impact]
  PR --> PM[MM-025 Project Memory]
  PM --> RM[MM-026 Room Mode]
  E --> LC[MM-027 Live collaboration]
  RM --> MT[MM-028 Meeting capture]
  MT --> ZM[MM-029 Zoom/Meet]
  PM --> BT[MM-030 Beats]
  CI --> DV[MM-031 Director/ShotIR]
  DV --> SB[MM-032 Storyboards]
  DV --> VL[MM-033 Visual language]
  SB --> PV[MM-034 Video previs]
  VL --> PV
  CO --> PB[MM-035 Breakdown]
  PB --> DH[MM-036 Department handoff]
  DH --> SC[MM-037 Schedule]
  SC --> BU[MM-038 Budget]
  BU --> IN[MM-039 Insurance readiness]
  CI --> AR[MM-040 Audience lab]
  CO --> RU[MM-041 Rubric]
  AR --> CF[MM-042 Commercial scenarios]
  RU --> CF
  BU --> CF
  CF --> ID[MM-043 Investor deck]
  DH --> API[MM-044 API/MCP]
  LC --> APPS[MM-045 Five platforms]
  API --> APPS
  ZM --> OPS[MM-046 Security/ops/evals]
  PV --> OPS
  IN --> OPS
  ID --> OPS
  APPS --> OPS
  C --> FINAL[MM-047 Final gate]
  UB --> FINAL
  RL --> FINAL
  BT --> FINAL
  OPS --> FINAL
```

## Corrected sequencing invariants

- `MM-009 Model router` is a prerequisite of `MM-017/018` and all later AI generation.
- `MM-012 Golden fixtures` exists before FDX, layout, editor regressions, and AI extraction acceptance.
- `MM-007 Generic artifacts` exists before storyboards, correspondence, insurance packets, and investor decks.
- `MM-035 Breakdown -> MM-037 Schedule -> MM-038 Budget -> MM-039 Insurance readiness` is mandatory.
- `MM-047` depends on every preceding package; it cannot hide an unfinished leaf package.

## Invalidation example

If the typed screenplay schema changes, `MM-002` becomes STALE. The tool computes reverse edges and marks its full dependent closure STALE—including document, revision, layout, FilmIR, production, platform, and final-gate items. Unrelated root tooling may remain PASS if its fingerprint did not change.
