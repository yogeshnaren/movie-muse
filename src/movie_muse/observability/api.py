"""Public surface of ``movie_muse.observability``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.observability.errors import ContentLeakageError, ObservabilityError, SloBreachError
from movie_muse.observability.index import INDEX_META_KEY
from movie_muse.observability.service import DEFAULT_SLOS, ObservabilityService, redact_attributes
from movie_muse.observability.types import (
    FORBIDDEN_ATTRIBUTE_KEYS,
    REDACTION_MARK,
    MetricSample,
    SloDefinition,
    TraceRecord,
)

__all__ = [
    "DEFAULT_SLOS",
    "FORBIDDEN_ATTRIBUTE_KEYS",
    "INDEX_META_KEY",
    "REDACTION_MARK",
    "ContentLeakageError",
    "MetricSample",
    "ObservabilityError",
    "ObservabilityService",
    "SloBreachError",
    "SloDefinition",
    "TraceRecord",
    "redact_attributes",
]
