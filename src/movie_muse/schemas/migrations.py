"""Migration hooks: ``schema_version`` field + ``migrate(from, to)`` interface.

Every domain payload carries a ``schema_version`` field (see the domain
dataclasses in this package). A :class:`MigrationRegistry` maps
``(schema_name, from_version) -> SchemaMigration`` so a payload can be walked
forward one step at a time to a target version. There is no default
fallback: an unregistered version jump raises :class:`MigrationPathError`
rather than guessing, which is the "fail closed" behavior required for a
breaking change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class MigrationPathError(LookupError):
    """Raised when no registered migration chain connects two versions."""


@dataclass(frozen=True)
class SchemaMigration:
    schema_name: str
    from_version: str
    to_version: str
    upgrade: Callable[[Mapping[str, Any]], dict[str, Any]]


class MigrationRegistry:
    """A directed graph of single-step schema migrations, keyed by schema name."""

    def __init__(self) -> None:
        self._edges: dict[tuple[str, str], SchemaMigration] = {}

    def register(self, migration: SchemaMigration) -> None:
        key = (migration.schema_name, migration.from_version)
        if key in self._edges:
            raise ValueError(
                f"a migration from {migration.schema_name} v{migration.from_version} is already registered"
            )
        self._edges[key] = migration

    def _find_path(self, schema_name: str, from_version: str, to_version: str) -> list[SchemaMigration]:
        path: list[SchemaMigration] = []
        current = from_version
        visited = {current}
        while current != to_version:
            step = self._edges.get((schema_name, current))
            if step is None:
                raise MigrationPathError(
                    f"no migration path for {schema_name} from v{from_version} to v{to_version} "
                    f"(stuck at v{current})"
                )
            path.append(step)
            current = step.to_version
            if current in visited:
                raise MigrationPathError(f"migration cycle detected for {schema_name} at v{current}")
            visited.add(current)
        return path

    def migrate(
        self,
        schema_name: str,
        payload: Mapping[str, Any],
        *,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        if from_version == to_version:
            return dict(payload)
        steps = self._find_path(schema_name, from_version, to_version)
        result: dict[str, Any] = dict(payload)
        for step in steps:
            result = step.upgrade(result)
            result["schema_version"] = step.to_version
        return result


#: The process-wide registry used by ``movie_muse.schemas.api``. Individual
#: schema modules or their tests register concrete migrations here; keeping
#: one shared instance means callers never need to know which module last
#: registered a given schema's migrations.
DEFAULT_REGISTRY = MigrationRegistry()


def _upgrade_rights_record_1_0_to_1_1(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Additive: introduce the optional ``license_expiry`` field."""

    upgraded = dict(payload)
    upgraded.setdefault("license_expiry", None)
    return upgraded


DEFAULT_REGISTRY.register(
    SchemaMigration(
        schema_name="rights_record",
        from_version="1.0",
        to_version="1.1",
        upgrade=_upgrade_rights_record_1_0_to_1_1,
    )
)


def _upgrade_collaboration_event_1_0_to_1_1(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Additive: introduce the optional ``promoted_project_memory_id`` field."""

    upgraded = dict(payload)
    upgraded.setdefault("promoted_project_memory_id", None)
    return upgraded


DEFAULT_REGISTRY.register(
    SchemaMigration(
        schema_name="collaboration_event",
        from_version="1.0",
        to_version="1.1",
        upgrade=_upgrade_collaboration_event_1_0_to_1_1,
    )
)
