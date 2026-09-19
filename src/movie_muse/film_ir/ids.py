"""Content-addressed FilmIR identifiers. Reprocessing the same revision is stable."""

from __future__ import annotations

import hashlib

from movie_muse.schemas.api import new_ulid

EXTRACTOR_VERSION = "film_ir/1.0.0"


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).digest()[:10]
    return f"{prefix}_{new_ulid(_time_ms=0, _random_bytes=digest)}"


def film_ir_id(project_id: str, revision_id: str, extractor_version: str) -> str:
    return _stable_id("fir", project_id, revision_id, extractor_version)


def entity_id(kind: str, canonical_name: str, revision_id: str) -> str:
    return _stable_id("firent", kind, canonical_name.casefold(), revision_id)


def claim_id(attribute: str, subject: str, revision_id: str) -> str:
    return _stable_id("cli", attribute, subject.casefold(), revision_id)


def evidence_id(film_ir: str, attribute: str, subject: str) -> str:
    return _stable_id("evb", film_ir, attribute, subject.casefold())
