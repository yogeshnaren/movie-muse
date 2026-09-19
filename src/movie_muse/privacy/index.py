"""Content-addressed privacy index."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from movie_muse.persistence.api import LocalWorkspace, digest_payload

INDEX_META_KEY = "privacy.index_digest"
INDEX_SCHEMA_VERSION = "1.0"
T = TypeVar("T")


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "erasure_ids": [],
        "erasure_digests": {},
        "erased_subjects": {},
        "training_opt_in": False,
        "residency": "us",
        "exports": {},
    }


def load_index(workspace: LocalWorkspace) -> dict[str, Any]:
    digest = workspace.store.get_meta(INDEX_META_KEY)
    if digest is None:
        return empty_index()
    decoded = json.loads(workspace.store.get_blob(digest).decode("utf-8"))
    if not isinstance(decoded, dict) or decoded.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ValueError("unsupported privacy index blob")
    return cast(dict[str, Any], decoded)


def mutate_index(workspace: LocalWorkspace, mutate: Callable[[dict[str, Any]], T]) -> T:
    with workspace.store.transaction():
        index = copy.deepcopy(load_index(workspace))
        result = mutate(index)
        encoded, digest = digest_payload(index)
        workspace.store.put_blob(encoded, expected_digest=digest)
        workspace.store.set_meta(INDEX_META_KEY, digest)
        return result
