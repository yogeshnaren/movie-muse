# ADR 0001 — Modular monolith plus durable workers

- Status: accepted
- Date: 2026-09-01
- Deciders: Movie Muse V2 architecture
- Work packages: MM-001

## Context

Movie Muse V2 must keep typed module boundaries, local-first persistence, durable
jobs, and a single versioned domain contract. Premature internal microservices would
split that contract without evidence.

## Decision

Ship a modular monolith under `src/movie_muse` with typed public `api` surfaces and
separate durable worker processes that share the same domain contract. Cross-module
table and internal imports are forbidden and tested. Internal service extraction
requires a later evidence-backed ADR.

## Evidence

- Architecture §2 forbids internal microservices without measured scaling, isolation,
  availability, or team-boundary evidence.
- MM-001 module-boundary tests fail on cross-module internal imports.
- Existing backend and frontend hosts remain application adapters over the monolith.

## Consequences

Teams can add modules without network boundaries. Independent deployability is
deferred. Worker and API processes may be deployed separately without becoming
independently versioned services.

## Alternatives considered

- Microservices-per-work-package: rejected; 47 packages are not 47 services.
- Single unstructured backend package: rejected; module boundaries would be
  unenforceable.
