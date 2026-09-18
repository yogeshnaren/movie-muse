"""Typed failures for the proposal engine."""

from __future__ import annotations


class ProposalEngineError(RuntimeError):
    """Base class for proposal/impact-review failures."""


class DirectCanonWriteError(ProposalEngineError):
    """AI or integration principals cannot write canon; they may only propose."""


class PartialAcceptError(ProposalEngineError):
    """Partial acceptance must name operation ids that exist on the proposal."""


class UnknownProposalError(ProposalEngineError):
    """Named proposal id is not in the workspace."""


class ProposalStateError(ProposalEngineError):
    """The proposal is not in a state that allows the requested lifecycle step."""
