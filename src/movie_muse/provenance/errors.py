"""Typed failures for provenance and Evidence Bundles."""

from __future__ import annotations


class ProvenanceError(RuntimeError):
    """Base class for fail-closed provenance errors."""


class EvidenceBundleNotFoundError(ProvenanceError):
    """An Evidence Bundle id is not present in the provenance index."""


class MissingCitationError(ProvenanceError):
    """A consequential claim was requested without a permitted citation."""


class ChainOfThoughtRejectedError(ProvenanceError):
    """Payloads must not include or claim to expose private chain-of-thought."""


class HumanValidationError(ProvenanceError):
    """Human-validation was requested by a non-human or unauthorized principal."""


class ExportDisclosureError(ProvenanceError):
    """Export of an Evidence Bundle disclosure failed closed."""
