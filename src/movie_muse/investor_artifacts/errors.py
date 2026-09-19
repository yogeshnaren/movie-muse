"""Typed failures for investor decks, one-pagers, and data rooms."""

from __future__ import annotations


class InvestorArtifactError(RuntimeError):
    """Base class for investor artifact failures."""


class PackNotFoundError(InvestorArtifactError):
    """The named investor pack is not in the index."""


class StaleEvidenceError(InvestorArtifactError):
    """Stale budget, forecast, or source artifacts cannot be exported as current."""


class UnsupportedClaimError(InvestorArtifactError):
    """Every claim/number must cite current reviewed evidence."""


class ApprovalRequiredError(InvestorArtifactError):
    """Creator approve is required before export or delivery."""


class FabricatedDeliveryError(InvestorArtifactError):
    """Credentials, attachments, and recipients must be real and present."""
