"""Append-only audit index stored as content-addressed blobs + workspace_meta."""

from __future__ import annotations

import copy
import json
from typing import Any

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "audit.index_digest"
INDEX_SCHEMA_VERSION = "1.0"


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "record_ids": [],
        "record_digests": {},
        "tail_hash": None,
        "next_sequence": 1,
    }


def load_index(workspace: LocalWorkspace) -> dict[str, Any] | None:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return None
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("audit index blob is not an object")
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
        raise ValueError("expected a JSON object blob")
    return payload
