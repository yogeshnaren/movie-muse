"""Treat retrieved text as data. Instruction-like payloads fail closed or redact."""

from __future__ import annotations

import re
from dataclasses import dataclass

from movie_muse.retrieval.errors import PromptInjectionError

_REJECT = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+|any\s+)?(previous|above|prior)\s+instructions",
        r"disregard\s+(your\s+|the\s+)?(safety|guidelines|rules|policy)",
        r"<\|im_start\|>",
        r"<\|system\|>",
        r"\[INST\]",
        r"^\s*system\s*:",
    )
)

_REDACT = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"you\s+are\s+now\b",
        r"act\s+as\s+(an?\s+)?(unrestricted|jailbroken|dan)\b",
        r"\bdeveloper\s+mode\b",
        r"\bdan\s+mode\b",
        r"new\s+instructions?\s*:",
    )
)

REDACTION_MARK = "[REDACTED_INSTRUCTION]"


@dataclass(frozen=True, slots=True)
class InjectionInspection:
    injected: bool
    severity: str
    redacted_text: str
    matched: tuple[str, ...]

    @property
    def rejected(self) -> bool:
        return self.severity == "reject"


def inspect_untrusted_text(text: str) -> InjectionInspection:
    """Classify instruction-like payloads without executing them."""

    matched: list[str] = []
    reject = False
    working = text
    for pattern in _REJECT:
        found = pattern.findall(working)
        if found or pattern.search(working):
            reject = True
            matched.append(pattern.pattern)
            working = pattern.sub(REDACTION_MARK, working)
    for pattern in _REDACT:
        if pattern.search(working):
            matched.append(pattern.pattern)
            working = pattern.sub(REDACTION_MARK, working)
    if not matched:
        return InjectionInspection(
            injected=False, severity="none", redacted_text=text, matched=()
        )
    remaining = working.replace(REDACTION_MARK, "").strip()
    if reject or not remaining:
        return InjectionInspection(
            injected=True,
            severity="reject",
            redacted_text=working,
            matched=tuple(matched),
        )
    return InjectionInspection(
        injected=True,
        severity="redact",
        redacted_text=working,
        matched=tuple(matched),
    )


def enforce_untrusted_text(text: str) -> InjectionInspection:
    """Redact instruction-like spans; fail closed when the payload is a takeover."""

    inspection = inspect_untrusted_text(text)
    if inspection.rejected:
        raise PromptInjectionError(
            "retrieved text is an instruction-like payload and cannot enter context"
        )
    return inspection
