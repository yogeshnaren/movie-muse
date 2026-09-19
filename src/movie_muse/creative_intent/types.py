"""Typed intent commands, envelopes, and merge results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import CreativeIntentIR, IntentScope, IntentSourceRole


class IntentKind(str, Enum):
    AUDIENCE_EXPERIENCE = "audience_experience"
    INFORMATION_STRATEGY = "information_strategy"
    THEME = "theme"
    TONE = "tone"
    POV = "pov"
    CHARACTER_INVARIANT = "character_invariant"
    PLOT_INVARIANT = "plot_invariant"
    VISUAL_RULE = "visual_rule"
    PERFORMANCE_RULE = "performance_rule"
    EXCEPTION = "exception"
    ANTI_RULE = "anti_rule"


class IntentAction(str, Enum):
    SET = "set"
    PRESERVE = "preserve"
    EXPLORE = "explore"
    VIOLATE = "violate"
    LOCK = "lock"
    UNLOCK = "unlock"


class IntentOrigin(str, Enum):
    DIRECT = "direct"
    CHAT = "chat"


def intent_key(
    *,
    branch_id: str,
    scope: IntentScope | str,
    scope_target_id: str,
    kind: IntentKind | str,
) -> str:
    scope_value = scope.value if isinstance(scope, IntentScope) else str(scope)
    kind_value = kind.value if isinstance(kind, IntentKind) else str(kind)
    return f"{branch_id}|{scope_value}|{scope_target_id}|{kind_value}"


@dataclass(frozen=True, slots=True)
class IntentCommand:
    """The only write path. Direct manipulation and chat emit this type."""

    action: IntentAction
    kind: IntentKind
    scope: IntentScope
    scope_target_id: str
    statement: str
    source_role: IntentSourceRole
    origin: IntentOrigin
    expected_revision_id: str
    branch_id: str
    project_id: str
    confidence: float = 1.0
    is_locked: bool = False
    exceptions: tuple[str, ...] = ()
    anti_rules: tuple[str, ...] = ()

    def canonical_payload(self) -> dict[str, Any]:
        """Origin-independent payload so chat and direct writes are the same command."""

        return {
            "action": self.action.value,
            "kind": self.kind.value,
            "scope": self.scope.value,
            "scope_target_id": self.scope_target_id,
            "statement": self.statement,
            "source_role": self.source_role.value,
            "expected_revision_id": self.expected_revision_id,
            "branch_id": self.branch_id,
            "project_id": self.project_id,
            "confidence": self.confidence,
            "is_locked": self.is_locked,
            "exceptions": list(self.exceptions),
            "anti_rules": list(self.anti_rules),
        }

    def with_origin(self, origin: IntentOrigin) -> IntentCommand:
        return IntentCommand(
            action=self.action,
            kind=self.kind,
            scope=self.scope,
            scope_target_id=self.scope_target_id,
            statement=self.statement,
            source_role=self.source_role,
            origin=origin,
            expected_revision_id=self.expected_revision_id,
            branch_id=self.branch_id,
            project_id=self.project_id,
            confidence=self.confidence,
            is_locked=self.is_locked,
            exceptions=self.exceptions,
            anti_rules=self.anti_rules,
        )


@dataclass(frozen=True, slots=True)
class IntentEnvelope:
    """Persisted wrapper around the versioned CreativeIntentIR schema object."""

    intent: CreativeIntentIR
    kind: IntentKind
    action: IntentAction
    origin: IntentOrigin
    confidence: float
    owner_actor_id: str
    branch_id: str
    superseded_id: str | None = None
    evolves_from_id: str | None = None

    @property
    def key(self) -> str:
        return intent_key(
            branch_id=self.branch_id,
            scope=self.intent.scope,
            scope_target_id=self.intent.scope_target_id,
            kind=self.kind,
        )

    @property
    def is_inferred(self) -> bool:
        return self.intent.source_role is IntentSourceRole.INFERRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "kind": self.kind.value,
            "action": self.action.value,
            "origin": self.origin.value,
            "confidence": self.confidence,
            "owner_actor_id": self.owner_actor_id,
            "branch_id": self.branch_id,
            "superseded_id": self.superseded_id,
            "evolves_from_id": self.evolves_from_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentEnvelope:
        superseded = data.get("superseded_id")
        evolves = data.get("evolves_from_id")
        return cls(
            intent=CreativeIntentIR.from_dict(dict(data["intent"])),
            kind=IntentKind(str(data["kind"])),
            action=IntentAction(str(data["action"])),
            origin=IntentOrigin(str(data["origin"])),
            confidence=float(data["confidence"]),
            owner_actor_id=str(data["owner_actor_id"]),
            branch_id=str(data["branch_id"]),
            superseded_id=str(superseded) if superseded is not None else None,
            evolves_from_id=str(evolves) if evolves is not None else None,
        )


@dataclass(frozen=True, slots=True)
class IntentRecord:
    envelope: IntentEnvelope
    stale: bool
    active: bool

    @property
    def intent(self) -> CreativeIntentIR:
        return self.envelope.intent


@dataclass(frozen=True, slots=True)
class IntentConflict:
    key: str
    source_id: str
    target_id: str
    source_statement: str
    target_statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "source_statement": self.source_statement,
            "target_statement": self.target_statement,
        }


@dataclass(frozen=True, slots=True)
class IntentMergeResult:
    copied_ids: tuple[str, ...]
    conflicts: tuple[IntentConflict, ...]

    @property
    def clean(self) -> bool:
        return not self.conflicts
