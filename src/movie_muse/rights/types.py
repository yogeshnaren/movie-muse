"""Immutable rights-registry records. Source versions are append-only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import RightsBasis, RightsRecord


class SourceClassification(str, Enum):
    USER_OWNED = "user_owned"
    PUBLIC_DOMAIN = "public_domain"
    LICENSED = "licensed"
    PERMITTED = "permitted"
    UNLICENSED = "unlicensed"
    DISALLOWED = "disallowed"


class PermittedUse(str, Enum):
    RETRIEVAL = "retrieval"
    CITATION = "citation"
    GENERATION = "generation"
    FORECAST = "forecast"
    EXPORT_DISCLOSURE = "export_disclosure"
    TRAINING = "training"


class SourceOrigin(str, Enum):
    HUMAN = "human"
    INTEGRATION = "integration"


class SourceValidationState(str, Enum):
    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"
    REJECTED = "rejected"


_BASIS_CLASSIFICATIONS = {
    SourceClassification.USER_OWNED: RightsBasis.USER_OWNED,
    SourceClassification.PUBLIC_DOMAIN: RightsBasis.PUBLIC_DOMAIN,
    SourceClassification.LICENSED: RightsBasis.LICENSED,
    SourceClassification.PERMITTED: RightsBasis.PERMITTED,
}


def classification_basis(classification: SourceClassification) -> RightsBasis | None:
    return _BASIS_CLASSIFICATIONS.get(classification)


def parse_permitted_use(value: PermittedUse | str) -> PermittedUse:
    return value if isinstance(value, PermittedUse) else PermittedUse(str(value))


def parse_classification(value: SourceClassification | str) -> SourceClassification:
    return value if isinstance(value, SourceClassification) else SourceClassification(str(value))


@dataclass(frozen=True, slots=True)
class SourceVersion:
    """One immutable version of a registered source."""

    id: str
    source_id: str
    version: int
    project_id: str
    title: str
    classification: SourceClassification
    permitted_uses: tuple[PermittedUse, ...]
    registered_by: str
    registered_at: str
    origin: SourceOrigin
    validation_state: SourceValidationState
    allow_training: bool = False
    uri: str | None = None
    license_summary: str | None = None
    license_expiry: str | None = None
    rights_record_id: str | None = None
    validated_by: str | None = None
    validated_at: str | None = None

    @property
    def basis(self) -> RightsBasis | None:
        return classification_basis(self.classification)

    @property
    def is_unlicensed(self) -> bool:
        return self.classification in {
            SourceClassification.UNLICENSED,
            SourceClassification.DISALLOWED,
        }

    @property
    def is_human_validated(self) -> bool:
        return (
            self.validation_state is SourceValidationState.VALIDATED
            and self.validated_by is not None
            and self.validated_at is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "version": self.version,
            "project_id": self.project_id,
            "title": self.title,
            "classification": self.classification.value,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "registered_by": self.registered_by,
            "registered_at": self.registered_at,
            "origin": self.origin.value,
            "validation_state": self.validation_state.value,
            "allow_training": self.allow_training,
            "uri": self.uri,
            "license_summary": self.license_summary,
            "license_expiry": self.license_expiry,
            "rights_record_id": self.rights_record_id,
            "validated_by": self.validated_by,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceVersion:
        return cls(
            id=str(data["id"]),
            source_id=str(data["source_id"]),
            version=int(data["version"]),
            project_id=str(data["project_id"]),
            title=str(data["title"]),
            classification=SourceClassification(str(data["classification"])),
            permitted_uses=tuple(
                PermittedUse(str(item)) for item in data.get("permitted_uses", ())
            ),
            registered_by=str(data["registered_by"]),
            registered_at=str(data["registered_at"]),
            origin=SourceOrigin(str(data["origin"])),
            validation_state=SourceValidationState(str(data["validation_state"])),
            allow_training=bool(data.get("allow_training", False)),
            uri=str(data["uri"]) if data.get("uri") is not None else None,
            license_summary=(
                str(data["license_summary"]) if data.get("license_summary") is not None else None
            ),
            license_expiry=(
                str(data["license_expiry"]) if data.get("license_expiry") is not None else None
            ),
            rights_record_id=(
                str(data["rights_record_id"]) if data.get("rights_record_id") is not None else None
            ),
            validated_by=(
                str(data["validated_by"]) if data.get("validated_by") is not None else None
            ),
            validated_at=(
                str(data["validated_at"]) if data.get("validated_at") is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class PermittedUseDecision:
    allowed: bool
    source_id: str
    version_id: str
    use: PermittedUse
    reason: str
    rights_record_id: str | None = None
    license_summary: str | None = None
    validation_state: SourceValidationState = SourceValidationState.UNVALIDATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "source_id": self.source_id,
            "version_id": self.version_id,
            "use": self.use.value,
            "reason": self.reason,
            "rights_record_id": self.rights_record_id,
            "license_summary": self.license_summary,
            "validation_state": self.validation_state.value,
        }


@dataclass(frozen=True, slots=True)
class SourceDisclosure:
    source_id: str
    version_id: str
    title: str
    classification: SourceClassification
    license_summary: str | None
    license_expiry: str | None
    permitted_uses: tuple[PermittedUse, ...]
    validation_state: SourceValidationState
    validated_by: str | None
    validated_at: str | None
    rights_record_id: str | None
    exported_at: str
    exported_by: str

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source_id": self.source_id,
            "version_id": self.version_id,
            "title": self.title,
            "classification": self.classification.value,
            "license_summary": self.license_summary,
            "license_expiry": self.license_expiry,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "validation_state": self.validation_state.value,
            "validated_by": self.validated_by,
            "validated_at": self.validated_at,
            "rights_record_id": self.rights_record_id,
            "exported_at": self.exported_at,
            "exported_by": self.exported_by,
        }
        assert "chain_of_thought" not in payload
        return payload


__all__ = [
    "PermittedUse",
    "PermittedUseDecision",
    "RightsBasis",
    "RightsRecord",
    "SourceClassification",
    "SourceDisclosure",
    "SourceOrigin",
    "SourceValidationState",
    "SourceVersion",
    "classification_basis",
    "parse_classification",
    "parse_permitted_use",
]
