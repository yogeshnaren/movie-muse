"""Typed dependency nodes, edges, hashes, and current/stale UI projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.jobs.api import Job
from movie_muse.schemas.api import DependencyNode

CODE_VERSION = "2.1.0"
SCHEMA_VERSION = "1.0"
RECOMPUTE_JOB_TYPE = "recompute_node"


class NodeKind(str, Enum):
    """Architecture §7 node kinds along the derived-data chain."""

    SOURCE_REVISION = "source_revision"
    ACCEPTED_CLAIM = "accepted_claim"
    CONFIGURATION = "configuration"
    MODEL = "model"
    RIGHTS_RECORD = "rights_record"
    DERIVED_PROJECTION = "derived_projection"
    ARTIFACT_VERSION = "artifact_version"


class NodeState(str, Enum):
    """Typed freshness. Stale data is viewable when labeled, never current."""

    CURRENT = "current"
    STALE = "stale"


SOURCE_KINDS = frozenset(
    {
        NodeKind.SOURCE_REVISION,
        NodeKind.ACCEPTED_CLAIM,
        NodeKind.CONFIGURATION,
        NodeKind.MODEL,
        NodeKind.RIGHTS_RECORD,
    }
)
DERIVED_KINDS = frozenset({NodeKind.DERIVED_PROJECTION, NodeKind.ARTIFACT_VERSION})


def parse_node_kind(value: NodeKind | str) -> NodeKind:
    if isinstance(value, NodeKind):
        return value
    try:
        return NodeKind(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown dependency node kind: {value!r}") from exc


def parse_node_state(value: NodeState | str) -> NodeState:
    if isinstance(value, NodeState):
        return value
    try:
        return NodeState(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown dependency node state: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class InputHashes:
    content_hash: str
    config_hash: str
    model_hash: str
    input_ids: tuple[str, ...]
    input_hashes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_hash": self.content_hash,
            "config_hash": self.config_hash,
            "model_hash": self.model_hash,
            "input_ids": list(self.input_ids),
            "input_hashes": list(self.input_hashes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputHashes:
        return cls(
            content_hash=str(data["content_hash"]),
            config_hash=str(data["config_hash"]),
            model_hash=str(data["model_hash"]),
            input_ids=tuple(str(item) for item in data.get("input_ids", ())),
            input_hashes=tuple(str(item) for item in data.get("input_hashes", ())),
        )


@dataclass(frozen=True, slots=True)
class StoredNode:
    """Module-owned node: schema DependencyNode plus content/config/model hashes."""

    record: DependencyNode
    kind: NodeKind
    state: NodeState
    content_hash: str
    config_hash: str
    model_hash: str
    provider_version: str | None = None
    subject_id: str | None = None
    queued_job_id: str | None = None
    generation: int = 0

    def __post_init__(self) -> None:
        if self.state is NodeState.STALE and not self.record.is_stale:
            raise ValueError("stale stored node must set DependencyNode.is_stale")
        if self.state is NodeState.CURRENT and self.record.is_stale:
            raise ValueError("current stored node cannot set DependencyNode.is_stale")

    @property
    def id(self) -> str:
        return self.record.id

    @property
    def project_id(self) -> str:
        return self.record.project_id

    @property
    def current(self) -> bool:
        return self.state is NodeState.CURRENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "kind": self.kind.value,
            "state": self.state.value,
            "content_hash": self.content_hash,
            "config_hash": self.config_hash,
            "model_hash": self.model_hash,
            "provider_version": self.provider_version,
            "subject_id": self.subject_id,
            "queued_job_id": self.queued_job_id,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredNode:
        record_raw = data["record"]
        if not isinstance(record_raw, dict):
            raise ValueError("stored node record is not an object")
        return cls(
            record=DependencyNode.from_dict(record_raw),
            kind=parse_node_kind(str(data["kind"])),
            state=parse_node_state(str(data["state"])),
            content_hash=str(data["content_hash"]),
            config_hash=str(data["config_hash"]),
            model_hash=str(data["model_hash"]),
            provider_version=(
                str(data["provider_version"]) if data.get("provider_version") else None
            ),
            subject_id=str(data["subject_id"]) if data.get("subject_id") else None,
            queued_job_id=str(data["queued_job_id"]) if data.get("queued_job_id") else None,
            generation=int(data.get("generation", 0)),
        )


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    id: str
    project_id: str
    from_id: str
    to_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyEdge:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            from_id=str(data["from_id"]),
            to_id=str(data["to_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class NodeView:
    """UI/state projection. Stale nodes are labeled and never reported as current."""

    id: str
    project_id: str
    kind: NodeKind
    state: NodeState
    current: bool
    labeled_stale: bool
    input_ids: tuple[str, ...]
    input_hashes: tuple[str, ...]
    content_hash: str
    config_hash: str
    model_hash: str
    code_version: str
    schema_version: str
    model_version: str | None
    provider_version: str | None
    prompt_template_version: str | None
    rights_snapshot_id: str | None
    produced_at: str
    subject_id: str | None = None
    queued_job_id: str | None = None

    def __post_init__(self) -> None:
        if self.state is NodeState.STALE:
            if self.current:
                raise ValueError("stale node cannot masquerade as current")
            if not self.labeled_stale:
                raise ValueError("stale node must be labeled")
        if self.state is NodeState.CURRENT:
            if not self.current:
                raise ValueError("current node must report current=true")
            if self.labeled_stale:
                raise ValueError("current node cannot be labeled stale")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "state": self.state.value,
            "current": self.current,
            "labeled_stale": self.labeled_stale,
            "input_ids": list(self.input_ids),
            "input_hashes": list(self.input_hashes),
            "content_hash": self.content_hash,
            "config_hash": self.config_hash,
            "model_hash": self.model_hash,
            "code_version": self.code_version,
            "schema_version": self.schema_version,
            "model_version": self.model_version,
            "provider_version": self.provider_version,
            "prompt_template_version": self.prompt_template_version,
            "rights_snapshot_id": self.rights_snapshot_id,
            "produced_at": self.produced_at,
            "subject_id": self.subject_id,
            "queued_job_id": self.queued_job_id,
        }


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    changed_ids: tuple[str, ...]
    frontier: tuple[str, ...]
    closure: tuple[str, ...]
    jobs: tuple[Job, ...]
    generation: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_ids": list(self.changed_ids),
            "frontier": list(self.frontier),
            "closure": list(self.closure),
            "job_ids": [job.id for job in self.jobs],
            "generation": self.generation,
        }


@dataclass(frozen=True, slots=True)
class RecomputeResult:
    node_id: str
    state: NodeState
    input_hashes: InputHashes
    produced_at: str
    skipped_upstream_stale: bool = False

    @property
    def current(self) -> bool:
        return self.state is NodeState.CURRENT


@dataclass(frozen=True, slots=True)
class ExportRecord:
    node_id: str
    state: NodeState
    current: bool
    labeled_stale: bool
    override: bool
    payload: dict[str, Any]
    audit_record_id: str | None = None

    def __post_init__(self) -> None:
        if self.state is NodeState.STALE and self.current:
            raise ValueError("stale export cannot masquerade as current")
