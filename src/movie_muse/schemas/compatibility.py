"""Compatibility policy: classify a schema change as additive or breaking.

Additive: existing required properties are untouched, existing property
*constraints* are unchanged, and only new *optional* properties are introduced.
Annotation-only edits (title/description/examples) are additive.

Breaking: a required property was removed or newly added, an existing
property vanished, an existing property's declared type or other constraint
changed (enum, const, ``$ref``, pattern, numeric/string bounds, nested
schema, combinators), or a previously-optional property became required.
This mirrors ordinary API/schema-evolution practice and is intentionally
conservative — when in doubt, a change is BREAKING, forcing an explicit
migration rather than a silent reinterpretation of old data.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# JSON Schema keywords that do not constrain instance validity.
_ANNOTATION_KEYS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "$comment",
        "$id",
        "$schema",
        "$anchor",
        "$vocabulary",
    }
)

_DEFINITION_KEYS = frozenset({"$defs", "definitions"})

# Compared as unordered collections of normalized values.
_UNORDERED_KEYS = frozenset({"enum", "required"})


class CompatibilityKind(str, Enum):
    ADDITIVE = "additive"
    BREAKING = "breaking"


def _normalize(value: Any, *, key: str | None = None) -> Any:
    """Canonicalize a JSON Schema fragment for constraint equality."""

    if isinstance(value, dict):
        return {
            child_key: _normalize(child, key=child_key)
            for child_key, child in sorted(value.items())
            if child_key not in _ANNOTATION_KEYS
        }
    if isinstance(value, list):
        normalized_items = [_normalize(item) for item in value]
        if key == "type" or key in _UNORDERED_KEYS:
            return tuple(sorted(normalized_items, key=repr))
        return normalized_items
    if key == "type":
        return (value,)
    return value


def constraints_equal(old_schema: Any, new_schema: Any) -> bool:
    """True when two schema fragments impose the same instance constraints."""

    return bool(_normalize(old_schema) == _normalize(new_schema))


def classify_schema_change(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> CompatibilityKind:
    """Classify moving from ``old_schema`` to ``new_schema`` as additive/breaking.

    Domain schemas in ``schemas/domain`` are ``type: object`` documents with a
    ``properties`` map and a ``required`` list. Nested property schemas are
    compared recursively so enum/const/$ref/pattern/bounds changes cannot be
    mistaken for additive evolution.
    """

    old_required = set(old_schema.get("required") or [])
    new_required = set(new_schema.get("required") or [])
    if new_required != old_required:
        return CompatibilityKind.BREAKING

    old_properties: dict[str, Any] = old_schema.get("properties") or {}
    new_properties: dict[str, Any] = new_schema.get("properties") or {}

    if set(old_properties) - set(new_properties):
        return CompatibilityKind.BREAKING

    for name in old_properties:
        if not constraints_equal(old_properties[name], new_properties[name]):
            return CompatibilityKind.BREAKING

    added = set(new_properties) - set(old_properties)
    if added & new_required:
        return CompatibilityKind.BREAKING

    old_rest = {
        key: value
        for key, value in old_schema.items()
        if key not in {"properties", "required"} | _DEFINITION_KEYS
    }
    new_rest = {
        key: value
        for key, value in new_schema.items()
        if key not in {"properties", "required"} | _DEFINITION_KEYS
    }
    if not constraints_equal(old_rest, new_rest):
        return CompatibilityKind.BREAKING

    for def_key in _DEFINITION_KEYS:
        old_defs: dict[str, Any] = old_schema.get(def_key) or {}
        new_defs: dict[str, Any] = new_schema.get(def_key) or {}
        if not isinstance(old_defs, dict) or not isinstance(new_defs, dict):
            if not constraints_equal(old_defs, new_defs):
                return CompatibilityKind.BREAKING
            continue
        if set(old_defs) - set(new_defs):
            return CompatibilityKind.BREAKING
        for name in old_defs:
            if not constraints_equal(old_defs[name], new_defs[name]):
                return CompatibilityKind.BREAKING

    return CompatibilityKind.ADDITIVE
