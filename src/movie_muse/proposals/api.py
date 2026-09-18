"""Public surface of ``movie_muse.proposals``.

Hosts and other modules must import this module, never sibling internals.
AI and integration principals may propose but cannot write canon.
"""

from __future__ import annotations

from movie_muse.proposals.errors import (
    DirectCanonWriteError,
    PartialAcceptError,
    ProposalEngineError,
    ProposalStateError,
    UnknownProposalError,
)
from movie_muse.proposals.service import ProposalService
from movie_muse.proposals.types import (
    AcceptResult,
    ProposalEnvelope,
    ProposalOrigin,
    ProposalReview,
)
from movie_muse.schemas.api import ImpactSummary, Proposal, ProposalStatus, RevalidationRecord

__all__ = [
    "AcceptResult",
    "DirectCanonWriteError",
    "ImpactSummary",
    "PartialAcceptError",
    "Proposal",
    "ProposalEngineError",
    "ProposalEnvelope",
    "ProposalOrigin",
    "ProposalReview",
    "ProposalService",
    "ProposalStateError",
    "ProposalStatus",
    "RevalidationRecord",
    "UnknownProposalError",
]
