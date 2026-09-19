"""Public surface of ``movie_muse.investor_artifacts``.

Hosts and other modules must import this module, never sibling internals.
Investor packs cite current evidence and require human approve before delivery.
"""

from __future__ import annotations

from movie_muse.investor_artifacts.errors import (
    ApprovalRequiredError,
    FabricatedDeliveryError,
    InvestorArtifactError,
    PackNotFoundError,
    StaleEvidenceError,
    UnsupportedClaimError,
)
from movie_muse.investor_artifacts.service import InvestorArtifactService, assert_no_fabrication
from movie_muse.investor_artifacts.types import (
    DISCLAIMER,
    FORBIDDEN_FABRICATION_PHRASES,
    Citation,
    CitedClaim,
    InvestorPack,
    PackKind,
    PackPreview,
)

__all__ = [
    "DISCLAIMER",
    "FORBIDDEN_FABRICATION_PHRASES",
    "ApprovalRequiredError",
    "Citation",
    "CitedClaim",
    "FabricatedDeliveryError",
    "InvestorArtifactError",
    "InvestorArtifactService",
    "InvestorPack",
    "PackKind",
    "PackNotFoundError",
    "PackPreview",
    "StaleEvidenceError",
    "UnsupportedClaimError",
    "assert_no_fabrication",
]
