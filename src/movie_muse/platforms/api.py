"""Public surface of ``movie_muse.platforms``.

Hosts must import this module, never sibling internals.
Every platform opens the same golden project identity against a live workspace.
"""

from __future__ import annotations

from movie_muse.platforms.errors import (
    CaptureConsentError,
    DeepLinkError,
    LongFormUnavailableError,
    PlatformError,
    StaticMockError,
)
from movie_muse.platforms.golden import (
    GOLDEN_ACTION_ID,
    GOLDEN_ACTOR_ID,
    GOLDEN_BRANCH_ID,
    GOLDEN_DOCUMENT_ID,
    GOLDEN_PROJECT_ID,
    GOLDEN_REVISION_ID,
    golden_project_and_document,
)
from movie_muse.platforms.parity import capabilities_for, parity_matrix
from movie_muse.platforms.service import PlatformApp, open_platform, resume_platform
from movie_muse.platforms.storage import WEB_DEFAULT_ORIGIN, prepare_storage, storage_root
from movie_muse.platforms.types import (
    ANNOTATION_BUDGET_SECONDS,
    DEEP_LINK_SCHEME,
    MIN_TOUCH_TARGET_PT,
    MOBILE_PLATFORMS,
    PARITY_AS_OF,
    PROFESSIONAL_PLATFORMS,
    UPDATE_CHANNEL,
    AccessibilityBudget,
    AnnotationResult,
    ParityRow,
    PlatformFocus,
    PlatformId,
    PlatformIdentity,
    ProtectionClass,
    StorageProfile,
)
from movie_muse.sync.api import SyncUploadBlockedError

__all__ = [
    "ANNOTATION_BUDGET_SECONDS",
    "DEEP_LINK_SCHEME",
    "GOLDEN_ACTION_ID",
    "GOLDEN_ACTOR_ID",
    "GOLDEN_BRANCH_ID",
    "GOLDEN_DOCUMENT_ID",
    "GOLDEN_PROJECT_ID",
    "GOLDEN_REVISION_ID",
    "MIN_TOUCH_TARGET_PT",
    "MOBILE_PLATFORMS",
    "PARITY_AS_OF",
    "PROFESSIONAL_PLATFORMS",
    "UPDATE_CHANNEL",
    "WEB_DEFAULT_ORIGIN",
    "AccessibilityBudget",
    "AnnotationResult",
    "CaptureConsentError",
    "DeepLinkError",
    "LongFormUnavailableError",
    "ParityRow",
    "PlatformApp",
    "PlatformError",
    "PlatformFocus",
    "PlatformId",
    "PlatformIdentity",
    "ProtectionClass",
    "StaticMockError",
    "StorageProfile",
    "SyncUploadBlockedError",
    "capabilities_for",
    "golden_project_and_document",
    "open_platform",
    "parity_matrix",
    "prepare_storage",
    "resume_platform",
    "storage_root",
]
