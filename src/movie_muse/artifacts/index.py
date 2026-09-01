"""Content-addressed artifact index stored through ``workspace_meta``."""

from __future__ import annotations

import copy
import json
from typing import Any

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "artifacts.index_digest"
INDEX_SCHEMA_VERSION = "1.0"


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "artifact_ids": [],
        "artifact_digests": {},
        "template_keys": [],
        "template_digests": {},
        "version_ids": [],
        "version_digests": {},
        "artifact_versions": {},
        "render_ids": [],
        "render_digests": {},
        "review_ids": [],
        "review_digests": {},
        "version_reviews": {},
        "link_ids": [],
        "link_digests": {},
        "delivery_ids": [],
        "delivery_digests": {},
    }


def load_index(workspace: LocalWorkspace) -> dict[str, Any]:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return empty_index()
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact index blob is not an object")
    return payload


def commit_index(workspace: LocalWorkspace, index: dict[str, Any]) -> str:
    encoded, digest = digest_payload(index)
    workspace.store.put_blob(encoded, expected_digest=digest)
    workspace.store.set_meta(INDEX_META_KEY, digest)
    return digest


def clone_index(index: dict[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = copy.deepcopy(index)
    return cloned


def put_json_blob(workspace: LocalWorkspace, payload: dict[str, Any]) -> str:
    encoded, digest = digest_payload(payload)
    workspace.store.put_blob(encoded, expected_digest=digest)
    return digest


def load_json_blob(workspace: LocalWorkspace, digest: str) -> dict[str, Any]:
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact record blob is not an object")
    return payload
