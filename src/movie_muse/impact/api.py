"""Public surface of ``movie_muse.impact``.

Hosts and other modules must import this module, never sibling internals.
Impact analysis does not call ModelRouter and does not write canon.
"""

from __future__ import annotations

from movie_muse.impact.errors import ImpactError
from movie_muse.impact.service import ImpactService
from movie_muse.schemas.api import ImpactSummary

__all__ = [
    "ImpactError",
    "ImpactService",
    "ImpactSummary",
]
