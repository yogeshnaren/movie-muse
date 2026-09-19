"""Dated parity matrix. Mobile is onset-first, not a static mock of desktop."""

from __future__ import annotations

from movie_muse.platforms.types import (
    MOBILE_PLATFORMS,
    PARITY_AS_OF,
    PROFESSIONAL_PLATFORMS,
    ParityRow,
    PlatformCapabilities,
    PlatformFocus,
    PlatformId,
)

_MOBILE_LIMITATIONS = (
    "iPhone and Android emphasize Room, capture, approvals, references, cards, "
    "and fast semantic annotations before full long-form authoring parity.",
    "Full professional screenplay pagination and long-form keyboard authoring "
    "remain on Web, macOS, and Windows.",
)

_DESKTOP_LIMITATIONS = (
    "On-set capture and large-target Room boards are available but are not the "
    "primary job for Web, macOS, or Windows.",
)


def parity_matrix(*, as_of: str = PARITY_AS_OF) -> tuple[ParityRow, ...]:
    rows: list[ParityRow] = []
    for platform in (PlatformId.WEB, PlatformId.MACOS, PlatformId.WINDOWS):
        rows.append(
            ParityRow(
                platform=platform,
                focus=PlatformFocus.PROFESSIONAL_AUTHORING,
                long_form=True,
                room=True,
                capture=False,
                cards=True,
                approvals=True,
                references=True,
                annotations=True,
                as_of=as_of,
            )
        )
    for platform in (PlatformId.IOS, PlatformId.ANDROID):
        rows.append(
            ParityRow(
                platform=platform,
                focus=PlatformFocus.ONSET_CAPTURE,
                long_form=False,
                room=True,
                capture=True,
                cards=True,
                approvals=True,
                references=True,
                annotations=True,
                as_of=as_of,
            )
        )
    return tuple(rows)


def capabilities_for(platform: PlatformId) -> PlatformCapabilities:
    professional = platform in PROFESSIONAL_PLATFORMS
    mobile = platform in MOBILE_PLATFORMS
    return PlatformCapabilities(
        long_form=professional,
        room=True,
        capture=mobile,
        cards=True,
        approvals=True,
        references=True,
        annotations=True,
        limitations=_DESKTOP_LIMITATIONS if professional else _MOBILE_LIMITATIONS,
    )
