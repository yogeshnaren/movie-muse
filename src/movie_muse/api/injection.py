"""Treat mesh tool/API text as data. Instruction-like payloads fail closed."""

from __future__ import annotations

from movie_muse.api.errors import InjectionRejectedError
from movie_muse.retrieval.api import inspect_untrusted_text

MESH_REJECT_PHRASES: tuple[str, ...] = (
    "bypass acl",
    "force accept",
    "force commit",
    "ignore previous",
    "you are now",
    "system override",
)


def assert_no_injection(*parts: str) -> None:
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        inspection = inspect_untrusted_text(cleaned)
        if inspection.rejected or inspection.injected:
            raise InjectionRejectedError(
                "untrusted mesh text looks like an instruction takeover"
            )
        lowered = cleaned.lower()
        for phrase in MESH_REJECT_PHRASES:
            if phrase in lowered:
                raise InjectionRejectedError(
                    f"untrusted mesh text contains a takeover phrase: {phrase}"
                )
