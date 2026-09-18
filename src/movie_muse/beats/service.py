"""Configurable beat frameworks with rights gates and mapping invalidation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.beats.errors import (
    CustomFrameworkError,
    FrameworkNotFoundError,
    FrameworkRightsError,
    SlotNotFoundError,
    ThemeContrastError,
    ThemeNotFoundError,
    UnlicensedFrameworkError,
)
from movie_muse.beats.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.beats.templates import CATALOG, KIND_SLOTS
from movie_muse.beats.types import (
    ADVISORY_DISCLAIMER,
    LICENSED_KINDS,
    MIN_CONTRAST_RATIO,
    BeatFramework,
    BeatSlot,
    CatalogEntry,
    ColorTheme,
    ColorToken,
    CompletionView,
    FrameworkKind,
    MappingStatus,
    SlotCompletion,
    SlotFill,
    SlotMapping,
    contrast_ratio,
)
from movie_muse.dependencies.api import DependencyEngine, NodeKind
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.rights.api import (
    PermittedUse,
    PermittedUseDeniedError,
    RightsService,
    UnlicensedSourceError,
)
from movie_muse.schemas.api import new_ulid


def _state_tokens(
    *,
    empty_bg: str,
    empty_fg: str,
    mapped_bg: str,
    mapped_fg: str,
    overridden_bg: str,
    overridden_fg: str,
    na_bg: str,
    na_fg: str,
    suggested_bg: str,
    suggested_fg: str,
) -> tuple[ColorToken, ...]:
    return (
        ColorToken("empty", empty_bg, empty_fg, "dotted", "Empty"),
        ColorToken("suggested", suggested_bg, suggested_fg, "dashed", "Suggested"),
        ColorToken("mapped", mapped_bg, mapped_fg, "solid", "Mapped"),
        ColorToken("overridden", overridden_bg, overridden_fg, "striped", "Overridden"),
        ColorToken("not_applicable", na_bg, na_fg, "hatched", "Not applicable"),
    )


def builtin_themes() -> tuple[ColorTheme, ...]:
    return (
        ColorTheme(
            id="thm_high_contrast_dark",
            name="High-contrast dark",
            tokens=_state_tokens(
                empty_bg="#111111",
                empty_fg="#F5F5F5",
                suggested_bg="#1B3A4B",
                suggested_fg="#F4FBFF",
                mapped_bg="#0B3D2E",
                mapped_fg="#F4FFF8",
                overridden_bg="#3D2E0B",
                overridden_fg="#FFF8E8",
                na_bg="#2A2A2A",
                na_fg="#EDEDED",
            ),
        ),
        ColorTheme(
            id="thm_high_contrast_light",
            name="High-contrast light",
            tokens=_state_tokens(
                empty_bg="#FFFFFF",
                empty_fg="#111111",
                suggested_bg="#D6ECF8",
                suggested_fg="#062433",
                mapped_bg="#D7F5E6",
                mapped_fg="#062817",
                overridden_bg="#F8E7C4",
                overridden_fg="#3A2504",
                na_bg="#E8E8E8",
                na_fg="#1A1A1A",
            ),
        ),
        ColorTheme(
            id="thm_deuteranopia_safe",
            name="Deuteranopia-safe",
            tokens=_state_tokens(
                empty_bg="#1A1A1A",
                empty_fg="#F7F7F7",
                suggested_bg="#003A70",
                suggested_fg="#F4F8FF",
                mapped_bg="#5C4B00",
                mapped_fg="#FFF8DC",
                overridden_bg="#5A2D82",
                overridden_fg="#F8F0FF",
                na_bg="#3A3A3A",
                na_fg="#F0F0F0",
            ),
        ),
    )


def _assert_accessible(theme: ColorTheme) -> None:
    for token in theme.tokens:
        ratio = contrast_ratio(token.foreground, token.background)
        if ratio < MIN_CONTRAST_RATIO:
            raise ThemeContrastError(
                f"theme {theme.id} token {token.key} contrast {ratio:.2f} < {MIN_CONTRAST_RATIO}"
            )
        if not token.pattern or not token.label:
            raise ThemeContrastError(
                f"theme {theme.id} token {token.key} must include pattern and text label"
            )


class BeatService:
    """Guidance-only beat mapping. Licensed names require rights. Override wins."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        rights: RightsService | None = None,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.rights = rights
        self.dependencies = dependencies
        self.clock = clock
        self._ensure_builtin_themes()

    def catalog(self) -> tuple[CatalogEntry, ...]:
        return CATALOG

    def list_themes(self) -> tuple[ColorTheme, ...]:
        index = load_index(self.workspace)
        themes: list[ColorTheme] = []
        for theme_id in index.get("theme_ids", ()):
            digest = dict(index.get("theme_digests", {})).get(str(theme_id))
            if digest is None:
                continue
            themes.append(ColorTheme.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(themes)

    def instantiate_framework(
        self,
        *,
        project_id: str,
        kind: FrameworkKind | str,
        principal: Principal,
        acl_epoch: int,
        source_id: str | None = None,
        custom_slots: Sequence[tuple[str, str, str]] = (),
        theme_id: str = "thm_high_contrast_dark",
        title: str | None = None,
    ) -> BeatFramework:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        parsed = kind if isinstance(kind, FrameworkKind) else FrameworkKind(str(kind))
        self._load_theme(theme_id)
        slot_defs = self._slot_defs(parsed, custom_slots)
        if parsed in LICENSED_KINDS:
            self._require_licensed_source(source_id)
        slots = tuple(
            BeatSlot(
                id=f"slot_{new_ulid()}",
                key=key,
                label=label,
                order=index,
                guidance=guidance,
            )
            for index, (key, label, guidance) in enumerate(slot_defs)
        )
        now = self.clock()
        framework = BeatFramework(
            id=f"fw_{new_ulid()}",
            project_id=project_id,
            kind=parsed,
            title=title or self._default_title(parsed),
            created_at=now,
            created_by_actor_id=principal.actor_id,
            slots=slots,
            theme_id=theme_id,
            source_id=source_id if parsed in LICENSED_KINDS else None,
        )
        stored = self._put_framework(framework)
        stored = self._attach_dependency_nodes(stored, principal, acl_epoch)
        self._audit(principal, acl_epoch, "beats.instantiate", stored.id, parsed.value)
        return stored

    def get_framework(
        self,
        framework_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> BeatFramework:
        framework = self._load(framework_id)
        self._require(principal, Action.READ, framework.project_id, acl_epoch)
        return framework

    def list_frameworks(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[BeatFramework, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        found: list[BeatFramework] = []
        for framework_id in index.get("framework_ids", ()):
            digest = dict(index.get("framework_digests", {})).get(str(framework_id))
            if digest is None:
                continue
            framework = BeatFramework.from_dict(load_payload(self.workspace, str(digest)))
            if framework.project_id == project_id:
                found.append(framework)
        return tuple(found)

    def apply_theme(
        self,
        framework_id: str,
        theme_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> BeatFramework:
        framework = self._load(framework_id)
        self._require(principal, Action.PROPOSE, framework.project_id, acl_epoch)
        self._load_theme(theme_id)
        updated = self._replace(framework, theme_id=theme_id)
        self._invalidate(updated, principal, acl_epoch)
        self._audit(principal, acl_epoch, "beats.apply_theme", framework_id, theme_id)
        return updated

    def register_theme(
        self,
        theme: ColorTheme,
        *,
        principal: Principal,
        project_id: str,
        acl_epoch: int,
    ) -> ColorTheme:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        _assert_accessible(theme)
        stored = self._put_theme(theme)
        self._audit(principal, acl_epoch, "beats.register_theme", theme.id, theme.name)
        return stored

    def suggest_mapping(
        self,
        framework_id: str,
        slot_key: str,
        *,
        scene_id: str,
        principal: Principal,
        acl_epoch: int,
        confidence: float = 0.5,
        story_function: str = "",
    ) -> SlotMapping:
        framework = self._writable(framework_id, principal, acl_epoch)
        slot = self._slot(framework, slot_key)
        existing = self._mapping_for(framework, slot_key)
        if existing is not None and existing.status in {
            MappingStatus.MAPPED,
            MappingStatus.OVERRIDDEN,
            MappingStatus.NOT_APPLICABLE,
        }:
            updated = SlotMapping(
                id=existing.id,
                framework_id=framework.id,
                slot_key=slot.key,
                status=existing.status,
                confidence=existing.confidence,
                scene_id=existing.scene_id,
                story_function=existing.story_function,
                suggested_scene_id=scene_id,
                override_reason=existing.override_reason,
                actor_id=existing.actor_id,
                updated_at=existing.updated_at,
            )
            self._upsert_mapping(framework, updated)
            return updated
        mapping = SlotMapping(
            id=existing.id if existing is not None else f"map_{new_ulid()}",
            framework_id=framework.id,
            slot_key=slot.key,
            status=MappingStatus.SUGGESTED,
            confidence=self._clamp_confidence(confidence),
            scene_id=None,
            story_function=story_function or slot.key,
            suggested_scene_id=scene_id,
            actor_id=principal.actor_id,
            updated_at=self.clock(),
        )
        stored_framework = self._upsert_mapping(framework, mapping)
        self._invalidate(stored_framework, principal, acl_epoch)
        self._audit(principal, acl_epoch, "beats.suggest_mapping", mapping.id, slot_key)
        return mapping

    def map_scene(
        self,
        framework_id: str,
        slot_key: str,
        *,
        scene_id: str,
        principal: Principal,
        acl_epoch: int,
        confidence: float = 1.0,
        story_function: str = "",
        override_reason: str = "",
    ) -> SlotMapping:
        framework = self._writable(framework_id, principal, acl_epoch)
        slot = self._slot(framework, slot_key)
        existing = self._mapping_for(framework, slot_key)
        suggested = existing.suggested_scene_id if existing is not None else None
        status = MappingStatus.MAPPED
        if suggested is not None and suggested != scene_id:
            status = MappingStatus.OVERRIDDEN
        if override_reason:
            status = MappingStatus.OVERRIDDEN
        mapping = SlotMapping(
            id=existing.id if existing is not None else f"map_{new_ulid()}",
            framework_id=framework.id,
            slot_key=slot.key,
            status=status,
            confidence=self._clamp_confidence(confidence),
            scene_id=scene_id,
            story_function=story_function or slot.key,
            suggested_scene_id=suggested,
            override_reason=override_reason,
            actor_id=principal.actor_id,
            updated_at=self.clock(),
        )
        stored_framework = self._upsert_mapping(framework, mapping)
        self._invalidate(stored_framework, principal, acl_epoch)
        self._audit(principal, acl_epoch, "beats.map_scene", mapping.id, status.value)
        return mapping

    def override_mapping(
        self,
        framework_id: str,
        slot_key: str,
        *,
        scene_id: str,
        reason: str,
        principal: Principal,
        acl_epoch: int,
        confidence: float = 1.0,
        story_function: str = "",
    ) -> SlotMapping:
        return self.map_scene(
            framework_id,
            slot_key,
            scene_id=scene_id,
            principal=principal,
            acl_epoch=acl_epoch,
            confidence=confidence,
            story_function=story_function,
            override_reason=reason or "manual override",
        )

    def mark_not_applicable(
        self,
        framework_id: str,
        slot_key: str,
        *,
        principal: Principal,
        acl_epoch: int,
        reason: str = "not applicable",
    ) -> SlotMapping:
        framework = self._writable(framework_id, principal, acl_epoch)
        slot = self._slot(framework, slot_key)
        existing = self._mapping_for(framework, slot_key)
        mapping = SlotMapping(
            id=existing.id if existing is not None else f"map_{new_ulid()}",
            framework_id=framework.id,
            slot_key=slot.key,
            status=MappingStatus.NOT_APPLICABLE,
            confidence=0.0,
            scene_id=None,
            story_function=slot.key,
            suggested_scene_id=existing.suggested_scene_id if existing is not None else None,
            override_reason=reason,
            actor_id=principal.actor_id,
            updated_at=self.clock(),
        )
        stored_framework = self._upsert_mapping(framework, mapping)
        self._invalidate(stored_framework, principal, acl_epoch)
        self._audit(principal, acl_epoch, "beats.not_applicable", mapping.id, slot_key)
        return mapping

    def completion_view(
        self,
        framework_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CompletionView:
        framework = self.get_framework(framework_id, principal=principal, acl_epoch=acl_epoch)
        by_key = {item.slot_key: item for item in framework.mappings}
        slots: list[SlotCompletion] = []
        applicable_confidences: list[float] = []
        mapped_count = 0
        applicable_count = 0
        for slot in framework.slots:
            mapping = by_key.get(slot.key)
            fill = SlotFill.EMPTY if mapping is None else SlotFill(mapping.status.value)
            if fill is SlotFill.NOT_APPLICABLE:
                text_status = "Not applicable"
            elif fill is SlotFill.OVERRIDDEN:
                text_status = "Overridden (manual mapping wins)"
                applicable_count += 1
                mapped_count += 1
                applicable_confidences.append(mapping.confidence if mapping else 0.0)
            elif fill is SlotFill.MAPPED:
                text_status = "Mapped"
                applicable_count += 1
                mapped_count += 1
                applicable_confidences.append(mapping.confidence if mapping else 0.0)
            elif fill is SlotFill.SUGGESTED:
                text_status = "Suggested only; not canon"
                applicable_count += 1
                applicable_confidences.append(0.0)
            else:
                text_status = "Empty"
                applicable_count += 1
                applicable_confidences.append(0.0)
            slots.append(
                SlotCompletion(
                    slot_key=slot.key,
                    label=slot.label,
                    fill=fill,
                    confidence=0.0 if mapping is None else mapping.confidence,
                    scene_id=None if mapping is None else mapping.scene_id,
                    color_token_key=fill.value,
                    text_status=text_status,
                )
            )
        mapped_ratio = (mapped_count / applicable_count) if applicable_count else 0.0
        mean_confidence = (
            sum(applicable_confidences) / len(applicable_confidences)
            if applicable_confidences
            else 0.0
        )
        return CompletionView(
            framework_id=framework.id,
            slots=tuple(slots),
            mapped_ratio=mapped_ratio,
            mean_confidence=mean_confidence,
            guidance_not_truth=True,
            disclaimer=framework.disclaimer or ADVISORY_DISCLAIMER,
            theme_id=framework.theme_id,
            formula_score=None,
        )

    def _slot_defs(
        self,
        kind: FrameworkKind,
        custom_slots: Sequence[tuple[str, str, str]],
    ) -> tuple[tuple[str, str, str], ...]:
        if kind is FrameworkKind.CUSTOM:
            if len(custom_slots) < 1:
                raise CustomFrameworkError("custom frameworks need at least one original slot")
            cleaned: list[tuple[str, str, str]] = []
            seen: set[str] = set()
            for key, label, guidance in custom_slots:
                slot_key = str(key).strip()
                if not slot_key or slot_key in seen:
                    raise CustomFrameworkError("custom slot keys must be unique and non-empty")
                seen.add(slot_key)
                cleaned.append((slot_key, str(label).strip() or slot_key, str(guidance)))
            return tuple(cleaned)
        return KIND_SLOTS[kind]

    def _default_title(self, kind: FrameworkKind) -> str:
        for entry in CATALOG:
            if entry.kind is kind:
                return entry.title
        return kind.value

    def _require_licensed_source(self, source_id: str | None) -> None:
        if not source_id:
            raise UnlicensedFrameworkError(
                "named licensed beat templates require a registered rights source"
            )
        if self.rights is None:
            raise UnlicensedFrameworkError(
                "named licensed beat templates require RightsService"
            )
        try:
            self.rights.require_permitted_use(source_id, PermittedUse.CITATION)
        except UnlicensedSourceError as exc:
            raise UnlicensedFrameworkError(str(exc)) from exc
        except PermittedUseDeniedError as exc:
            raise FrameworkRightsError(str(exc)) from exc

    def _attach_dependency_nodes(
        self,
        framework: BeatFramework,
        principal: Principal,
        acl_epoch: int,
    ) -> BeatFramework:
        if self.dependencies is None:
            return framework
        config = self.dependencies.add_node(
            project_id=framework.project_id,
            kind=NodeKind.CONFIGURATION,
            principal=principal,
            acl_epoch=acl_epoch,
            subject_id=framework.id,
        )
        analysis = self.dependencies.add_node(
            project_id=framework.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config.id,),
            subject_id=framework.id,
        )
        return self._replace(
            framework,
            config_node_id=config.id,
            analysis_node_id=analysis.id,
        )

    def _invalidate(
        self,
        framework: BeatFramework,
        principal: Principal,
        acl_epoch: int,
    ) -> None:
        if self.dependencies is None or not framework.config_node_id:
            return
        self.dependencies.invalidate_inputs(
            [framework.config_node_id],
            principal=principal,
            acl_epoch=acl_epoch,
        )

    def _writable(
        self, framework_id: str, principal: Principal, acl_epoch: int
    ) -> BeatFramework:
        framework = self._load(framework_id)
        self._require(principal, Action.PROPOSE, framework.project_id, acl_epoch)
        return framework

    def _slot(self, framework: BeatFramework, slot_key: str) -> BeatSlot:
        for slot in framework.slots:
            if slot.key == slot_key:
                return slot
        raise SlotNotFoundError(f"slot {slot_key} is not on framework {framework.id}")

    def _mapping_for(self, framework: BeatFramework, slot_key: str) -> SlotMapping | None:
        for mapping in framework.mappings:
            if mapping.slot_key == slot_key:
                return mapping
        return None

    def _upsert_mapping(self, framework: BeatFramework, mapping: SlotMapping) -> BeatFramework:
        mappings = tuple(
            mapping if item.slot_key == mapping.slot_key else item for item in framework.mappings
        )
        if mapping.slot_key not in {item.slot_key for item in framework.mappings}:
            mappings = (*framework.mappings, mapping)
        return self._replace(framework, mappings=mappings)

    def _clamp_confidence(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)

    def _ensure_builtin_themes(self) -> None:
        index = load_index(self.workspace)
        missing = [
            theme
            for theme in builtin_themes()
            if theme.id not in set(index.get("theme_ids", ()))
        ]
        if not missing:
            return
        for theme in missing:
            _assert_accessible(theme)
            self._put_theme(theme)

    def _load_theme(self, theme_id: str) -> ColorTheme:
        index = load_index(self.workspace)
        digest = dict(index.get("theme_digests", {})).get(theme_id)
        if digest is None:
            raise ThemeNotFoundError(f"theme {theme_id} is not registered")
        theme = ColorTheme.from_dict(load_payload(self.workspace, str(digest)))
        _assert_accessible(theme)
        return theme

    def _load(self, framework_id: str) -> BeatFramework:
        index = load_index(self.workspace)
        digest = dict(index.get("framework_digests", {})).get(framework_id)
        if digest is None:
            raise FrameworkNotFoundError(f"framework {framework_id} is not in the index")
        return BeatFramework.from_dict(load_payload(self.workspace, str(digest)))

    def _put_framework(self, framework: BeatFramework) -> BeatFramework:
        def persist(index: dict[str, Any]) -> BeatFramework:
            digest = put_payload(self.workspace, framework.to_dict())
            ids = list(index["framework_ids"])
            if framework.id not in ids:
                ids.append(framework.id)
            index["framework_ids"] = ids
            digests = dict(index["framework_digests"])
            digests[framework.id] = digest
            index["framework_digests"] = digests
            return framework

        return mutate_index(self.workspace, persist)

    def _put_theme(self, theme: ColorTheme) -> ColorTheme:
        def persist(index: dict[str, Any]) -> ColorTheme:
            digest = put_payload(self.workspace, theme.to_dict())
            ids = list(index["theme_ids"])
            if theme.id not in ids:
                ids.append(theme.id)
            index["theme_ids"] = ids
            digests = dict(index["theme_digests"])
            digests[theme.id] = digest
            index["theme_digests"] = digests
            return theme

        return mutate_index(self.workspace, persist)

    def _replace(self, framework: BeatFramework, **changes: Any) -> BeatFramework:
        payload = framework.to_dict()
        for key, value in changes.items():
            if isinstance(value, tuple):
                payload[key] = [
                    item.to_dict() if hasattr(item, "to_dict") else item for item in value
                ]
            elif isinstance(value, Enum):
                payload[key] = value.value
            else:
                payload[key] = value
        return self._put_framework(BeatFramework.from_dict(payload))

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="beat_framework",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
