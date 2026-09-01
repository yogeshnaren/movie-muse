"""Public surface of the ``movie_muse.schemas`` module.

Per ``config/module-layout.yaml``, other modules and application hosts
(``backend/app``, ``frontend/src``) must import only
``movie_muse.schemas.api``. Every other module in this package (``document``,
``events``, ``epistemic``, ``ids``, ...) is an implementation detail; the
module-boundary scanner in ``movie_muse.toolchain.boundaries`` rejects any
cross-module import that does not end in ``.api``.
"""

from __future__ import annotations

from movie_muse.schemas.artifact import Artifact, ArtifactStatus, ArtifactVersion
from movie_muse.schemas.change_set import ChangeSet, ChangeSetOperation, OperationType
from movie_muse.schemas.collaboration import (
    CollaborationEvent,
    CollaborationRecordKind,
    PromotionState,
)
from movie_muse.schemas.compatibility import CompatibilityKind, classify_schema_change
from movie_muse.schemas.creative_intent import CreativeIntentIR, IntentScope, IntentSourceRole
from movie_muse.schemas.dependency_node import DependencyNode
from movie_muse.schemas.document import (
    Attachment,
    Block,
    BlockKind,
    InlineSpan,
    Note,
    ProductionTag,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
)
from movie_muse.schemas.epistemic import (
    EPISTEMIC_TYPES_BY_LEVEL,
    AuthoredFact,
    EpistemicLevel,
    InferredClaim,
    OperationalAssumption,
    ScenarioOutput,
    StructuralFact,
)
from movie_muse.schemas.events import EVENT_TYPES, ProjectEvent, compute_integrity_hash
from movie_muse.schemas.evidence import CitedSource, EvidenceBundle, HumanValidationState
from movie_muse.schemas.film_ir import FilmIR, FilmIrEntity, FilmIrEntityKind
from movie_muse.schemas.ids import (
    ID_KIND_PREFIXES,
    ActorId,
    ArtifactId,
    ArtifactVersionId,
    AttachmentId,
    AuthoredFactId,
    BlockId,
    BranchId,
    ChangeSetId,
    CharacterCueId,
    CollaborationEventId,
    CreativeIntentId,
    DependencyNodeId,
    DialoguePairId,
    DocumentId,
    EventId,
    EvidenceBundleId,
    FilmIrId,
    InferredClaimId,
    InlineSpanId,
    NoteId,
    OperationalAssumptionId,
    ProductionProjectionId,
    ProductionTagId,
    ProjectId,
    ProjectMemoryId,
    ProposalId,
    RevisionId,
    RevisionMarkId,
    RightsRecordId,
    ScenarioModelId,
    ScenarioOutputId,
    SceneId,
    SceneSpaceId,
    SequenceId,
    ShotId,
    StructuralFactId,
    is_valid_id,
    new_id,
    new_ulid,
    parse_id_kind,
    require_id,
)
from movie_muse.schemas.migrations import (
    DEFAULT_REGISTRY,
    MigrationPathError,
    MigrationRegistry,
    SchemaMigration,
)
from movie_muse.schemas.production import BudgetMaturity, ProductionProjection, ProjectionKind
from movie_muse.schemas.project import Project, ProjectStatus
from movie_muse.schemas.project_memory import ProjectMemory, ProjectMemoryKind
from movie_muse.schemas.proposal import ImpactSummary, Proposal, ProposalStatus, RevalidationRecord
from movie_muse.schemas.rights import RightsBasis, RightsRecord
from movie_muse.schemas.scenario import ScenarioModel, ScenarioOutcome
from movie_muse.schemas.scene_space import SceneSpace, SubjectPosition
from movie_muse.schemas.serialization import dataclass_to_dict, to_json_dict
from movie_muse.schemas.shot_ir import CameraSpec, ShotIR
from movie_muse.schemas.validators import (
    SchemaNotFoundError,
    ValidationError,
    domain_schema_dir,
    get_validator,
    validate_payload,
)

__all__ = [
    # ids
    "ID_KIND_PREFIXES",
    "ActorId",
    "ArtifactId",
    "ArtifactVersionId",
    "AttachmentId",
    "AuthoredFactId",
    "BlockId",
    "BranchId",
    "ChangeSetId",
    "CharacterCueId",
    "CollaborationEventId",
    "CreativeIntentId",
    "DependencyNodeId",
    "DialoguePairId",
    "DocumentId",
    "EventId",
    "EvidenceBundleId",
    "FilmIrId",
    "InferredClaimId",
    "InlineSpanId",
    "NoteId",
    "OperationalAssumptionId",
    "ProductionProjectionId",
    "ProductionTagId",
    "ProjectId",
    "ProjectMemoryId",
    "ProposalId",
    "RevisionId",
    "RevisionMarkId",
    "RightsRecordId",
    "ScenarioModelId",
    "ScenarioOutputId",
    "SceneId",
    "SceneSpaceId",
    "SequenceId",
    "ShotId",
    "StructuralFactId",
    "is_valid_id",
    "new_id",
    "new_ulid",
    "parse_id_kind",
    "require_id",
    # epistemic
    "EPISTEMIC_TYPES_BY_LEVEL",
    "AuthoredFact",
    "EpistemicLevel",
    "InferredClaim",
    "OperationalAssumption",
    "ScenarioOutput",
    "StructuralFact",
    # compatibility + migrations
    "CompatibilityKind",
    "classify_schema_change",
    "DEFAULT_REGISTRY",
    "MigrationPathError",
    "MigrationRegistry",
    "SchemaMigration",
    # validators
    "SchemaNotFoundError",
    "ValidationError",
    "domain_schema_dir",
    "get_validator",
    "validate_payload",
    # serialization
    "dataclass_to_dict",
    "to_json_dict",
    # project
    "Project",
    "ProjectStatus",
    # screenplay document kernel shape
    "Attachment",
    "Block",
    "BlockKind",
    "InlineSpan",
    "Note",
    "ProductionTag",
    "RevisionMark",
    "ScreenplayDocument",
    "Sequence",
    # change set / proposal
    "ChangeSet",
    "ChangeSetOperation",
    "OperationType",
    "ImpactSummary",
    "Proposal",
    "ProposalStatus",
    "RevalidationRecord",
    # events
    "EVENT_TYPES",
    "ProjectEvent",
    "compute_integrity_hash",
    # evidence + rights + collaboration
    "CitedSource",
    "EvidenceBundle",
    "HumanValidationState",
    "RightsBasis",
    "RightsRecord",
    "CollaborationEvent",
    "CollaborationRecordKind",
    "PromotionState",
    # film graph
    "FilmIR",
    "FilmIrEntity",
    "FilmIrEntityKind",
    "CreativeIntentIR",
    "IntentScope",
    "IntentSourceRole",
    "ProjectMemory",
    "ProjectMemoryKind",
    # visual/production/scenario
    "CameraSpec",
    "ShotIR",
    "SceneSpace",
    "SubjectPosition",
    "BudgetMaturity",
    "ProductionProjection",
    "ProjectionKind",
    "ScenarioModel",
    "ScenarioOutcome",
    # artifacts + dependency graph
    "Artifact",
    "ArtifactStatus",
    "ArtifactVersion",
    "DependencyNode",
]
