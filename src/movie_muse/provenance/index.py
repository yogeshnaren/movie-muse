"""Content-addressed provenance index stored through ``workspace_meta``."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "provenance.index_digest"
INDEX_SCHEMA_VERSION = "1.0"

T = TypeVar("T")


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "bundle_ids": [],
        "bundle_digests": {},
        "validation_ids": [],
        "validation_digests": {},
        "bundle_validations": {},
        "disclosure_ids": [],
        "disclosure_digests": {},
        "artifact_links": {},
    }


def load_index(workspace: LocalWorkspace) -> dict[str, Any]:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return empty_index()
    decoded = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(decoded, dict) or decoded.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ValueError("unsupported provenance index blob")
    return cast(dict[str, Any], decoded)


def mutate_index(
    workspace: LocalWorkspace,
    mutate: Callable[[dict[str, Any]], T],
) -> T:
    """Serialize provenance index changes and atomically replace its digest pointer."""

    with workspace.store.transaction():
        index = copy.deepcopy(load_index(workspace))
        result = mutate(index)
        encoded, digest = digest_payload(index)
        workspace.store.put_blob(encoded, expected_digest=digest)
        workspace.store.set_meta(INDEX_META_KEY, digest)
        return result


def put_payload(workspace: LocalWorkspace, payload: dict[str, Any]) -> str:
    encoded, digest = digest_payload(payload)
    workspace.store.put_blob(encoded, expected_digest=digest)
    return digest


def load_payload(workspace: LocalWorkspace, digest: str) -> dict[str, Any]:
    decoded = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("provenance record blob is not an object")
    return decoded
