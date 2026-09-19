"""Public surface of ``movie_muse.retrieval``.

Hosts and other modules must import this module, never sibling internals.
Retrieved text is data. Instruction-like payloads fail closed or redact.
"""

from __future__ import annotations

from movie_muse.retrieval.errors import (
    PromptInjectionError,
    ReferenceNotFoundError,
    RetrievalError,
    TenantIsolationError,
)
from movie_muse.retrieval.injection import (
    REDACTION_MARK,
    InjectionInspection,
    enforce_untrusted_text,
    inspect_untrusted_text,
)
from movie_muse.retrieval.service import RetrievalService
from movie_muse.retrieval.types import Citation, IndexedReference, RetrievedSegment

__all__ = [
    "REDACTION_MARK",
    "Citation",
    "IndexedReference",
    "InjectionInspection",
    "PromptInjectionError",
    "ReferenceNotFoundError",
    "RetrievalError",
    "RetrievalService",
    "RetrievedSegment",
    "TenantIsolationError",
    "enforce_untrusted_text",
    "inspect_untrusted_text",
]
