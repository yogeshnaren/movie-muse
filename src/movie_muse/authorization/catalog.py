"""Authorization-owned catalog of operations and artifacts.

Documents and branches are resolved from persistence/revisions. Artifacts and
operations have no dedicated MM-006 store, so this catalog is the fail-closed
existence authority until later packages bind real objects.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "authorization.resource_catalog_digest"
INDEX_SCHEMA_VERSION = "1.0"


def empty_catalog() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "operations": {},
        "artifacts": {},
    }


def load_catalog(workspace: LocalWorkspace) -> dict[str, Any]:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return empty_catalog()
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authorization resource catalog blob is not an object")
    return payload


def commit_catalog(workspace: LocalWorkspace, catalog: dict[str, Any]) -> str:
    encoded, digest = digest_payload(catalog)
    workspace.store.put_blob(encoded, expected_digest=digest)
    workspace.store.set_meta(INDEX_META_KEY, digest)
    return digest


def clone_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = copy.deepcopy(catalog)
    return cloned
