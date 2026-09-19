"""Typed failures for insurance readiness support packages."""

from __future__ import annotations


class InsuranceReadinessError(RuntimeError):
    """Base class for insurance-readiness failures."""


class PacketNotFoundError(InsuranceReadinessError):
    """The named readiness packet is not in the index."""


class StaleInputsError(InsuranceReadinessError):
    """Stale budget or schedule cannot be labeled current readiness."""


class HandoffNotAuthorizedError(InsuranceReadinessError):
    """Broker handoff requires preview, approval, and explicit confirm."""


class CoverageClaimError(InsuranceReadinessError):
    """The packet is readiness support, not underwriting, binding, or coverage."""
