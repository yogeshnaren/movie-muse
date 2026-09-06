"""Model-independent budget fitting. No tokenizer or ModelRouter."""

from __future__ import annotations

from dataclasses import replace

from movie_muse.context.errors import ContextBudgetExceededError
from movie_muse.context.types import ContextBudget, ContextSegment, SegmentKind

_PRIORITY = {
    SegmentKind.REVISION: 0,
    SegmentKind.INTENT: 1,
    SegmentKind.MEMORY: 2,
    SegmentKind.AUTHORED_FACT: 3,
    SegmentKind.STRUCTURAL_FACT: 4,
    SegmentKind.INFERRED_CLAIM: 5,
    SegmentKind.OPERATIONAL_ASSUMPTION: 6,
    SegmentKind.SCENARIO_OUTPUT: 7,
    SegmentKind.REFERENCE: 8,
}


def segment_char_count(text: str) -> int:
    return len(text)


def segment_byte_count(text: str) -> int:
    return len(text.encode("utf-8"))


def _truncate(text: str, max_chars: int, max_bytes: int) -> str:
    if max_chars < 1 or max_bytes < 1:
        return ""
    clipped = text[:max_chars]
    encoded = clipped.encode("utf-8")
    while encoded and len(encoded) > max_bytes:
        clipped = clipped[:-1]
        encoded = clipped.encode("utf-8")
    return clipped


def fit_segments(
    segments: tuple[ContextSegment, ...] | list[ContextSegment],
    budget: ContextBudget,
) -> tuple[ContextSegment, ...]:
    ordered = sorted(segments, key=lambda item: (_PRIORITY[item.kind], item.source_id, item.id))
    selected: list[ContextSegment] = []
    chars = 0
    bytes_used = 0
    for segment in ordered:
        if len(selected) >= budget.max_segments:
            break
        extra_chars = segment_char_count(segment.text)
        extra_bytes = segment_byte_count(segment.text)
        if (
            chars + extra_chars <= budget.max_chars
            and bytes_used + extra_bytes <= budget.max_bytes
        ):
            selected.append(segment)
            chars += extra_chars
            bytes_used += extra_bytes
            continue
        remaining_chars = budget.max_chars - chars
        remaining_bytes = budget.max_bytes - bytes_used
        truncated = _truncate(segment.text, remaining_chars, remaining_bytes)
        if not truncated:
            if segment.kind is SegmentKind.REVISION and not selected:
                raise ContextBudgetExceededError(
                    "budget cannot fit a required revision segment and its source ids"
                )
            break
        selected.append(replace(segment, text=truncated, truncated=True))
        break
    if not selected:
        raise ContextBudgetExceededError(
            "budget cannot retain any citation-bearing context segment"
        )
    return tuple(selected)


def bundle_counts(segments: tuple[ContextSegment, ...]) -> tuple[int, int]:
    text = "".join(segment.text for segment in segments)
    return segment_char_count(text), segment_byte_count(text)
