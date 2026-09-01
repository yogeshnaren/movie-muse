"""RightsRecord — the Rights Registry's unit of provenance and permitted use.

Architecture §14: Reference Lens may only retrieve user-owned, public-domain,
licensed, or otherwise permitted sources registered here; every surfaced
reference must display source and rights context.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class RightsBasis(str, Enum):
    USER_OWNED = "user_owned"
    PUBLIC_DOMAIN = "public_domain"
    LICENSED = "licensed"
    PERMITTED = "permitted"


@sealed
@dataclass(frozen=True, slots=True)
class RightsRecord:
    SCHEMA_NAME: ClassVar[str] = "rights_record"

    id: str
    source_id: str
    basis: RightsBasis
    owner_actor_id: str
    registered_at: str
    allow_training: bool = False
    license_summary: str | None = None
    license_expiry: str | None = None
    schema_version: str = "1.1"

    def __post_init__(self) -> None:
        if self.allow_training and self.basis not in (RightsBasis.USER_OWNED, RightsBasis.LICENSED):
            raise ValueError(
                "allow_training requires an explicit user_owned or licensed rights basis, "
                "never implied consent"
            )

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RightsRecord:
        return dataclass_from_dict(cls, data, converters={"basis": RightsBasis})
