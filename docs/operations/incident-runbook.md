# Incident runbook (MM-046)

Use this drill for backup/restore and severity handling. Closing an incident
without an independent reproduction is forbidden.

## Steps

1. Classify severity (low/medium/high/critical). Open high/critical security
   findings must be resolved before `assert_ready`.
2. Snapshot the workspace with `OperationsService.backup`.
3. Restore into a separate directory with `restore_into`.
4. Verify sqlite (`movie_muse.sqlite`) and content-addressed blobs.
5. Reproduce the drill independently from the backup (second restore root).
6. Close the incident only when `independently_reproduced` is true.

## Cost and SBOM

- Paid spend is recorded under `Action.RUN_PAID_PROVIDER` and cannot exceed
  the declared cap.
- Generate an SBOM from `pyproject.toml` and `requirements-dev.txt` before
  treating the workspace as operable.

This runbook is operational readiness support. It is not an underwriting or
coverage statement.
