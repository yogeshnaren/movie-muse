"""JSON Schema (Draft 2020-12) loading, cross-file $ref resolution, and validation.

Schema files live in ``schemas/domain/*.schema.json`` and reference shared
``$defs`` in ``common.schema.json`` (stable-id patterns, timestamps, schema
versions, epistemic levels) via relative ``$ref``. This module builds one
``referencing.Registry`` from every schema file's declared ``$id`` so those
relative refs resolve regardless of which schema is validated first.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]
from referencing import Registry, Resource

from movie_muse.toolchain.paths import repo_root

__all__ = [
    "ValidationError",
    "SchemaNotFoundError",
    "domain_schema_dir",
    "load_schema_documents",
    "build_registry",
    "get_validator",
    "validate_payload",
]


class SchemaNotFoundError(KeyError):
    """Raised when a named domain schema file does not exist."""


def domain_schema_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "schemas" / "domain"


def _schema_filename(schema_name: str) -> str:
    return f"{schema_name}.schema.json"


@cache
def load_schema_documents(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return every ``schemas/domain/*.schema.json`` document keyed by its ``$id``."""

    schema_dir = domain_schema_dir(root)
    documents: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        schema_id = document["$id"]
        documents[schema_id] = document
    return documents


@cache
def build_registry(root: Path | None = None) -> Registry[Any]:
    documents = load_schema_documents(root)
    resources = [(schema_id, Resource.from_contents(doc)) for schema_id, doc in documents.items()]
    registry: Registry[Any] = Registry().with_resources(resources)
    return registry


def _schema_id_for_name(schema_name: str, root: Path | None) -> str:
    schema_dir = domain_schema_dir(root)
    path = schema_dir / _schema_filename(schema_name)
    if not path.is_file():
        raise SchemaNotFoundError(schema_name)
    document = json.loads(path.read_text(encoding="utf-8"))
    schema_id: str = document["$id"]
    return schema_id


def get_validator(schema_name: str, *, root: Path | None = None) -> Draft202012Validator:
    """Return a compiled validator for ``schema_name`` (e.g. ``"project"``)."""

    registry = build_registry(root)
    schema_id = _schema_id_for_name(schema_name, root)
    schema = registry.contents(schema_id)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=registry)


def validate_payload(schema_name: str, payload: dict[str, Any], *, root: Path | None = None) -> None:
    """Validate ``payload`` against ``schema_name``; raises ``ValidationError`` on failure."""

    get_validator(schema_name, root=root).validate(payload)
    if schema_name == "proposal":
        change_set = payload.get("change_set") or {}
        if payload.get("base_revision_id") != change_set.get("base_revision_id"):
            raise ValidationError(
                "proposal base_revision_id must match change_set.base_revision_id"
            )


def clear_schema_cache() -> None:
    """Drop cached schema documents/registries (mainly for test isolation)."""

    load_schema_documents.cache_clear()
    build_registry.cache_clear()
