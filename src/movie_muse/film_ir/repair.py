"""Repair invalid structured extraction once, then fail closed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from movie_muse.film_ir.errors import ExtractionRepairError
from movie_muse.model_router.api import StructuredOutputError

_COT_KEYS = frozenset(
    {
        "chain_of_thought",
        "chain-of-thought",
        "chainOfThought",
        "private_cot",
        "thinking",
        "<thinking>",
    }
)


def _contains_chain_of_thought(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in _COT_KEYS or _contains_chain_of_thought(inner)
            for key, inner in value.items()
        )
    if isinstance(value, list | tuple):
        return any(_contains_chain_of_thought(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "chain-of-thought" in lowered or "chain_of_thought" in lowered
    return False

_REQUIRED = ("entities", "method", "assumptions", "uncertainty")


def repair_extraction_output(raw: object) -> dict[str, Any]:
    """Normalize adapter JSON. One repair pass; still-invalid output fails."""

    if _contains_chain_of_thought(raw):
        raise StructuredOutputError("extraction output contained chain-of-thought")
    if not isinstance(raw, Mapping):
        raise ExtractionRepairError("extraction output is not an object")
    payload = dict(raw)
    if "entities" not in payload or not isinstance(payload.get("entities"), list):
        raise ExtractionRepairError("extraction output is missing an entities array")
    payload.setdefault("method", "repaired")
    if not isinstance(payload.get("assumptions"), list):
        payload["assumptions"] = ["repaired_missing_assumptions"]
    payload.setdefault("uncertainty", "repaired")
    cleaned: list[dict[str, str]] = []
    for item in payload["entities"]:
        if not isinstance(item, Mapping):
            raise ExtractionRepairError("entity row is not an object")
        name = str(item.get("name") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        if not name or not kind:
            raise ExtractionRepairError("entity row is missing name or kind")
        cleaned.append({"name": name, "kind": kind})
    payload["entities"] = cleaned
    missing = [key for key in _REQUIRED if key not in payload]
    if missing:
        raise ExtractionRepairError(f"extraction output still missing {missing}")
    return payload
