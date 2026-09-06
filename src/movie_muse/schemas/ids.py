"""Stable, sortable, kind-distinct identifiers for the domain constitution.

Every canonical entity kind gets its own :class:`typing.NewType` so mypy treats
IDs from different entity kinds as nominally incompatible even though they
share the same runtime representation (``str``). IDs are lexicographically
sortable ULIDs (48-bit millisecond timestamp + 80 bits of randomness, encoded
with the Crockford base32 alphabet) so creation order is recoverable without a
central sequence, which matters for local-first, offline-capable clients.

The kind -> prefix mapping here MUST stay in sync with
``schemas/domain/common.schema.json``; ``tests/schemas/test_ids.py`` asserts
that consistency so the two representations cannot silently drift apart.
"""

from __future__ import annotations

import os
import re
import time
from typing import Final, NewType

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# entity kind -> stable, short, lowercase prefix. Keep alphabetically grouped
# by the acceptance-criteria entity list, then the supporting domain kinds.
ID_KIND_PREFIXES: Final[dict[str, str]] = {
    "document": "doc",
    "sequence": "seq",
    "block": "blk",
    "inline_span": "spn",
    "scene": "scn",
    "character_cue": "cue",
    "dialogue_pair": "dlg",
    "note": "note",
    "revision_mark": "rvm",
    "production_tag": "ptg",
    "attachment": "att",
    "project": "proj",
    "revision": "rev",
    "branch": "brn",
    "actor": "act",
    "event": "evt",
    "change_set": "cst",
    "proposal": "prp",
    "evidence_bundle": "evb",
    "rights_record": "rgt",
    "collaboration_event": "cev",
    "shot": "sht",
    "scene_space": "ssp",
    "production_projection": "opj",
    "scenario_model": "scm",
    "artifact": "art",
    "artifact_version": "avr",
    "dependency_node": "dep",
    "project_memory": "mem",
    "film_ir": "fir",
    "creative_intent": "cin",
    "authored_fact": "fca",
    "structural_fact": "fcs",
    "inferred_claim": "cli",
    "operational_assumption": "aso",
    "scenario_output": "osc",
}

_PREFIX_TO_KIND: Final[dict[str, str]] = {v: k for k, v in ID_KIND_PREFIXES.items()}


def _id_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(prefix)}_[0-9A-HJKMNP-TV-Z]{{26}}$")


ID_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    kind: _id_pattern(prefix) for kind, prefix in ID_KIND_PREFIXES.items()
}


def _encode_crockford(value: int, length: int) -> str:
    chars = ["0"] * length
    for index in range(length - 1, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    if value:
        raise OverflowError("value does not fit in the requested ULID field width")
    return "".join(chars)


def new_ulid(*, _time_ms: int | None = None, _random_bytes: bytes | None = None) -> str:
    """Return a 26-character Crockford-base32 ULID (time-sortable, 128 bits)."""

    ms = _time_ms if _time_ms is not None else int(time.time() * 1000)
    randomness = _random_bytes if _random_bytes is not None else os.urandom(10)
    if len(randomness) != 10:
        raise ValueError("ULID randomness component must be exactly 10 bytes")
    time_part = _encode_crockford(ms, 10)
    random_int = int.from_bytes(randomness, byteorder="big")
    random_part = _encode_crockford(random_int, 16)
    return time_part + random_part


def new_id(kind: str) -> str:
    """Mint a new stable ID for ``kind`` (e.g. ``"scene"`` -> ``"scn_<ulid>"``)."""

    if kind not in ID_KIND_PREFIXES:
        raise ValueError(f"unknown stable id kind: {kind!r}")
    return f"{ID_KIND_PREFIXES[kind]}_{new_ulid()}"


def is_valid_id(kind: str, value: str) -> bool:
    pattern = ID_PATTERNS.get(kind)
    if pattern is None:
        raise ValueError(f"unknown stable id kind: {kind!r}")
    return bool(pattern.match(value))


def parse_id_kind(value: str) -> str:
    """Return the entity kind encoded in ``value``'s prefix, or raise ``ValueError``."""

    prefix, _, _rest = value.partition("_")
    kind = _PREFIX_TO_KIND.get(prefix)
    if kind is None or not is_valid_id(kind, value):
        raise ValueError(f"not a recognized stable id: {value!r}")
    return kind


def require_id(kind: str, value: str, *, field_name: str = "id") -> str:
    """Validate ``value`` is a well-formed ``kind`` id and return it unchanged."""

    if not is_valid_id(kind, value):
        raise ValueError(f"{field_name} is not a valid {kind} id: {value!r}")
    return value


# Kind-distinct NewTypes. mypy rejects passing one where another is expected
# even though every one of them is a plain ``str`` at runtime.
DocumentId = NewType("DocumentId", str)
SequenceId = NewType("SequenceId", str)
BlockId = NewType("BlockId", str)
InlineSpanId = NewType("InlineSpanId", str)
SceneId = NewType("SceneId", str)
CharacterCueId = NewType("CharacterCueId", str)
DialoguePairId = NewType("DialoguePairId", str)
NoteId = NewType("NoteId", str)
RevisionMarkId = NewType("RevisionMarkId", str)
ProductionTagId = NewType("ProductionTagId", str)
AttachmentId = NewType("AttachmentId", str)
ProjectId = NewType("ProjectId", str)
RevisionId = NewType("RevisionId", str)
BranchId = NewType("BranchId", str)
ActorId = NewType("ActorId", str)
EventId = NewType("EventId", str)
ChangeSetId = NewType("ChangeSetId", str)
ProposalId = NewType("ProposalId", str)
EvidenceBundleId = NewType("EvidenceBundleId", str)
RightsRecordId = NewType("RightsRecordId", str)
CollaborationEventId = NewType("CollaborationEventId", str)
ShotId = NewType("ShotId", str)
SceneSpaceId = NewType("SceneSpaceId", str)
ProductionProjectionId = NewType("ProductionProjectionId", str)
ScenarioModelId = NewType("ScenarioModelId", str)
ArtifactId = NewType("ArtifactId", str)
ArtifactVersionId = NewType("ArtifactVersionId", str)
DependencyNodeId = NewType("DependencyNodeId", str)
ProjectMemoryId = NewType("ProjectMemoryId", str)
FilmIrId = NewType("FilmIrId", str)
CreativeIntentId = NewType("CreativeIntentId", str)
AuthoredFactId = NewType("AuthoredFactId", str)
StructuralFactId = NewType("StructuralFactId", str)
InferredClaimId = NewType("InferredClaimId", str)
OperationalAssumptionId = NewType("OperationalAssumptionId", str)
ScenarioOutputId = NewType("ScenarioOutputId", str)
