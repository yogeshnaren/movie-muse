"""Compatibility policy: classify a schema change as additive or breaking.

Additive: existing required properties are untouched, existing property
types are unchanged, and only new *optional* properties are introduced.
Breaking: a required property was removed or newly added, an existing
property's declared type changed, or a previously-optional property became
required. This mirrors ordinary API/schema-evolution practice and is
intentionally conservative — when in doubt, a change is BREAKING, forcing an
explicit migration rather than a silent reinterpretation of old data.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class CompatibilityKind(str, Enum):
    ADDITIVE = "additive"
    BREAKING = "breaking"


def _property_type(schema: dict[str, Any]) -> Any:
    return schema.get("type") if isinstance(schema, dict) else None


def classify_schema_change(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> CompatibilityKind:
    """Classify moving from ``old_schema`` to ``new_schema`` as additive/breaking.

    Both schemas are expected to be flat ``type: object`` documents with a
    ``properties`` map and a ``required`` list, which is how every domain
    schema in ``schemas/domain`` is shaped at its top level.
    """

    old_required = set(old_schema.get("required") or [])
    new_required = set(new_schema.get("required") or [])
    old_properties: dict[str, Any] = old_schema.get("properties") or {}
    new_properties: dict[str, Any] = new_schema.get("properties") or {}

    if new_required - old_required:
        return CompatibilityKind.BREAKING
    if old_required - new_required:
        # A previously required field became optional or vanished: treat as
        # breaking unless the field also still exists as optional (soft
        # deprecation). Outright removal from `properties` is breaking below.
        return CompatibilityKind.BREAKING

    removed_properties = set(old_properties) - set(new_properties)
    if removed_properties:
        return CompatibilityKind.BREAKING

    for name in set(old_properties) & set(new_properties):
        if _property_type(old_properties[name]) != _property_type(new_properties[name]):
            return CompatibilityKind.BREAKING

    return CompatibilityKind.ADDITIVE
