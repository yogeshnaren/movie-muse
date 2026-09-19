# Threat model (MM-046)

Movie Muse is a modular monolith with a durable worker. The control plane
treats tenant isolation, classification, encryption, and prompt-injection as
fail-closed local authorities.

## Assets

- Canonical FilmIR, CreativeIntentIR, revisions, and approved artifacts
- Identity, membership, and ACL snapshots
- Sealed secrets (local PBKDF2-derived keys or customer BYOK)
- Privacy erasure and export records
- Evaluation traces and operational backups

## Adversaries

- Cross-tenant principals (same process, different organization/project)
- Role confusion (viewer/writer attempting ACL, export, or financial read)
- Tampered sealed blobs
- Instruction-like retrieval text and egress payloads
- Remote providers receiving confidential/restricted data
- Cost overruns and incomplete incident recovery

## Controls

- `AuthorizationService.require` denies missing grants; viewer is READ only
- HIGH/CRITICAL threat findings block `SecurityService.assert_ready`
- Classification ranks: public=0, internal=1, confidential=2, restricted=3;
  remote providers may serve at most internal
- Stdlib SHA-256 counter-mode plus HMAC-SHA256; BYOK and private-route keys
  fail closed when absent
- `inspect_untrusted_text` rejects takeover payloads
- Privacy no-training default remains on until `MANAGE_ACL` opt-in
- Telemetry redacts prompt/secret keys; content leakage fails closed
- Backup/restore and incident close require an independently reproduced drill
- SBOM is generated from declared pins; denied packages fail closed

This document is a readiness control surface, not a penetration-test report
for a live multi-tenant SaaS deployment.
