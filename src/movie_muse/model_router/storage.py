"""Content-addressed model-router index stored through ``workspace_meta``."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "model_router.index_digest"
INDEX_SCHEMA_VERSION = "1.0"

T = TypeVar("T")


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "decision_ids": [],
        "decision_digests": {},
        "quote_ids": [],
        "quote_digests": {},
        "usage_ids": [],
        "usage_digests": {},
        "prompt_keys": [],
        "prompt_digests": {},
        "cache": {},
        "fine_tuned_adapters": {},
    }


def load_index(workspace: LocalWorkspace) -> dict[str, Any]:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return empty_index()
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ValueError("unsupported model_router index blob")
    return cast(dict[str, Any], payload)


def mutate_index(
    workspace: LocalWorkspace,
    mutate: Callable[[dict[str, Any]], T],
) -> T:
    with workspace.store.transaction():
        index = copy.deepcopy(load_index(workspace))
        result = mutate(index)
        encoded, digest = digest_payload(index)
        workspace.store.put_blob(encoded, expected_digest=digest)
        workspace.store.set_meta(INDEX_META_KEY, digest)
        return result


def put_json_blob(workspace: LocalWorkspace, payload: dict[str, Any]) -> str:
    encoded, digest = digest_payload(payload)
    workspace.store.put_blob(encoded, expected_digest=digest)
    return digest


def load_json_blob(workspace: LocalWorkspace, digest: str) -> dict[str, Any]:
    payload = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("model_router record blob is not an object")
    return payload
