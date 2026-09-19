"""Platform identity, parity, storage, and accessibility contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

PARITY_AS_OF = "2026-09-19"
API_SURFACE = "movie_muse.platforms.api"
ANNOTATION_BUDGET_SECONDS = 2.0
MIN_TOUCH_TARGET_PT = 44
DEEP_LINK_SCHEME = "moviemuse"
UPDATE_CHANNEL = "stable"


class PlatformId(str, Enum):
    WEB = "web"
    MACOS = "macos"
    WINDOWS = "windows"
    IOS = "ios"
    ANDROID = "android"


class PlatformFocus(str, Enum):
    PROFESSIONAL_AUTHORING = "professional_authoring"
    ONSET_CAPTURE = "onset_capture"


PROFESSIONAL_PLATFORMS: frozenset[PlatformId] = frozenset(
    {PlatformId.WEB, PlatformId.MACOS, PlatformId.WINDOWS}
)
MOBILE_PLATFORMS: frozenset[PlatformId] = frozenset({PlatformId.IOS, PlatformId.ANDROID})


class ProtectionClass(str, Enum):
    ORIGIN_ISOLATED = "origin_isolated"
    APPLICATION_SUPPORT_0700 = "application_support_0700"
    LOCALAPPDATA_RESTRICTED = "localappdata_restricted"
    NSFILEPROTECTION_COMPLETE = "NSFileProtectionComplete"
    MODE_PRIVATE = "MODE_PRIVATE"


@dataclass(frozen=True, slots=True)
class ParityRow:
    platform: PlatformId
    focus: PlatformFocus
    long_form: bool
    room: bool
    capture: bool
    cards: bool
    approvals: bool
    references: bool
    annotations: bool
    as_of: str = PARITY_AS_OF

    def to_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload["platform"] = self.platform.value
        payload["focus"] = self.focus.value
        return payload


@dataclass(frozen=True, slots=True)
class StorageProfile:
    platform: PlatformId
    root: str
    protection: ProtectionClass
    mode: int
    origin: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload["platform"] = self.platform.value
        payload["protection"] = self.protection.value
        return payload


@dataclass(frozen=True, slots=True)
class AccessibilityBudget:
    min_touch_target_pt: int = MIN_TOUCH_TARGET_PT
    annotation_budget_seconds: float = ANNOTATION_BUDGET_SECONDS
    large_target: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    platform: PlatformId
    project_id: str
    document_id: str
    revision_id: str
    branch_id: str
    layout_hash: str
    layout_engine_version: str

    def to_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload["platform"] = self.platform.value
        return payload


@dataclass(frozen=True, slots=True)
class AnnotationResult:
    note_id: str
    latency_seconds: float
    within_budget: bool
    target_pt: int

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    long_form: bool
    room: bool
    capture: bool
    cards: bool
    approvals: bool
    references: bool
    annotations: bool
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload["limitations"] = list(self.limitations)
        return payload
