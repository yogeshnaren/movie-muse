"""Public surface of ``movie_muse.privacy``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.privacy.errors import (
    CrossUserCacheError,
    ErasedError,
    PrivacyError,
    RetentionError,
    TrainingConsentError,
)
from movie_muse.privacy.index import INDEX_META_KEY
from movie_muse.privacy.service import PrivacyService
from movie_muse.privacy.types import (
    CROSS_USER_PROMPT_CACHE,
    NO_TRAINING_DEFAULT,
    PROVIDER_RETENTION,
    ErasureRecord,
    Residency,
    SubjectExport,
    TrainingPolicy,
)

__all__ = [
    "CROSS_USER_PROMPT_CACHE",
    "INDEX_META_KEY",
    "NO_TRAINING_DEFAULT",
    "PROVIDER_RETENTION",
    "CrossUserCacheError",
    "ErasedError",
    "ErasureRecord",
    "PrivacyError",
    "PrivacyService",
    "Residency",
    "RetentionError",
    "SubjectExport",
    "TrainingConsentError",
    "TrainingPolicy",
]
