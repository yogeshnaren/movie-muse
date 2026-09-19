# Competitive workflow matrix

Dated: 2026-09-05  
Owner: MM-016  
Canonical machine-readable source: `docs/competitive/workflow-matrix.yaml`

This matrix records **observable Movie Muse tasks** against professional
expectations represented by Final Draft, Celtx, Arc Studio, Filmustage, and
Scriptation. It does **not** claim UI, feature, or product equivalence.

| Result | Meaning |
|---|---|
| `supported` | Movie Muse performs the task. An automated test is release-blocking. |
| `gap` | The task is specified and owned by a later package. Not supported yet. |
| `external` | Requires a licensed/manual/sandbox gate that is not recorded. |

Manual or missing external evidence remains **release-blocking** for
`verify_all.sh` / MM-047. It must not be marked PASS by inventing a live gate.

Do not add competitor sample files. Use MM-012 fixtures only.

See `docs/competitive/PROTOCOL.md` for how each protocol is run.
