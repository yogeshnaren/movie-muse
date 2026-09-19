"""Deterministic schedules over locked breakdowns. Hard constraints fail closed."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.breakdown.api import (
    BreakdownElement,
    BreakdownService,
    ElementKind,
    StaleBreakdownError,
    StoredBreakdown,
)
from movie_muse.compiler.api import CompilerService
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.scheduling.engine import DEFAULT_SCENE_MINUTES, join_conflict, pack
from movie_muse.scheduling.errors import (
    InfeasibleScheduleError,
    ScheduleNotFoundError,
    StaleScheduleError,
    StripNotFoundError,
)
from movie_muse.scheduling.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.scheduling.types import (
    AvailabilityBlock,
    Board,
    Conflict,
    DayPart,
    Pin,
    ResourceKind,
    SceneDemand,
    ScheduleScenario,
    StoredSchedule,
    Strip,
)
from movie_muse.schemas.api import (
    ProductionProjection,
    ProjectionKind,
    new_id,
    new_ulid,
)


class ScheduleService:
    """Compile strips/boards from a breakdown. Breakdown changes stale the schedule."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        revisions: RevisionService,
        breakdown: BreakdownService,
        *,
        compiler: CompilerService | None = None,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.revisions = revisions
        self.breakdown = breakdown
        self.compiler = compiler or CompilerService()
        self.dependencies = dependencies
        self.clock = clock

    def compile(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        seed: int = 1,
        schedule_id: str | None = None,
    ) -> StoredSchedule:
        stored_breakdown = self.breakdown.get_breakdown(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.PROPOSE, stored_breakdown.projection.project_id, acl_epoch)
        if stored_breakdown.labeled_stale or stored_breakdown.projection.is_stale:
            raise StaleBreakdownError("cannot compile a schedule from a stale breakdown")
        existing = (
            self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
            if schedule_id
            else None
        )
        pins = existing.pins if existing else ()
        availability = existing.availability if existing else ()
        durations = dict(existing.durations) if existing else {}
        demands = self._demands(stored_breakdown, durations)
        packed = pack(
            demands,
            seed=seed,
            pins={item.scene_id: item.board_index for item in pins},
            blocked=tuple(
                (item.kind, item.name, item.board_index) for item in availability
            ),
        )
        boards = self._boards(packed.placements)
        projection_id = existing.projection.id if existing else new_id("production_projection")
        schedule = StoredSchedule(
            projection=ProductionProjection(
                id=projection_id,
                project_id=stored_breakdown.projection.project_id,
                kind=ProjectionKind.SCHEDULE,
                source_revision_id=stored_breakdown.locked_revision_id,
                computed_at=self.clock(),
                data={
                    "breakdown_id": stored_breakdown.projection.id,
                    "seed": seed,
                    "board_count": len(boards),
                },
                is_stale=False,
            ),
            breakdown_id=stored_breakdown.projection.id,
            seed=seed,
            boards=boards,
            demands=demands,
            pins=pins,
            availability=availability,
            durations=durations,
            infeasible=packed.infeasible,
            conflicts=packed.conflicts,
            labeled_stale=False,
            config_node_id=existing.config_node_id if existing else None,
            analysis_node_id=existing.analysis_node_id if existing else None,
        )
        written = self._put(schedule)
        if written.config_node_id is None:
            written = self._attach_dependency_nodes(written, principal, acl_epoch)
        self._audit(principal, acl_epoch, "schedule.compile", written.id, str(seed))
        return written

    def get_schedule(
        self, schedule_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredSchedule:
        stored = self._load(schedule_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def pin(
        self,
        schedule_id: str,
        scene_id: str,
        board_index: int,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredSchedule:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._demand(stored, scene_id)
        pins = tuple(
            item for item in stored.pins if item.scene_id != scene_id
        ) + (Pin(scene_id=scene_id, board_index=board_index),)
        updated = self._repack(stored, pins=pins)
        written = self._put(updated)
        self._audit(principal, acl_epoch, "schedule.pin", written.id, scene_id)
        return written

    def block_resource(
        self,
        schedule_id: str,
        kind: ResourceKind | str,
        name: str,
        board_index: int,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredSchedule:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        parsed = kind if isinstance(kind, ResourceKind) else ResourceKind(str(kind))
        block = AvailabilityBlock(kind=parsed, name=name, board_index=board_index)
        availability = stored.availability + (block,)
        updated = self._repack(stored, availability=availability)
        written = self._put(updated)
        self._audit(principal, acl_epoch, "schedule.block_resource", written.id, name)
        return written

    def set_scene_duration(
        self,
        schedule_id: str,
        scene_id: str,
        minutes: int,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredSchedule:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._demand(stored, scene_id)
        durations = dict(stored.durations)
        durations[scene_id] = int(minutes)
        updated = self._repack(stored, durations=durations)
        written = self._put(updated)
        self._audit(principal, acl_epoch, "schedule.set_duration", written.id, scene_id)
        return written

    def move_scene(
        self,
        schedule_id: str,
        scene_id: str,
        board_index: int,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredSchedule:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        moving = self._demand(stored, scene_id)
        occupants = tuple(
            strip.scene
            for board in stored.boards
            if board.index == board_index
            for strip in board.strips
            if strip.scene.scene_id != scene_id
        )
        previous_night = tuple(
            name
            for board in stored.boards
            if board.index == board_index - 1
            for strip in board.strips
            if strip.scene.day_part.value == "night"
            for name in strip.scene.cast
        )
        conflict = join_conflict(
            moving,
            occupants,
            board_index=board_index,
            previous_night_cast=previous_night,
            blocked=tuple(
                (item.kind, item.name, item.board_index) for item in stored.availability
            ),
        )
        if conflict is not None:
            raise InfeasibleScheduleError(
                "manual move would silently break a hard constraint",
                explanations=(conflict.explanation,),
            )
        trial_pins = tuple(
            item for item in stored.pins if item.scene_id != scene_id
        ) + (Pin(scene_id=scene_id, board_index=board_index),)
        trial = self._repack(stored, pins=trial_pins)
        if any(scene_id in item.scene_ids for item in trial.infeasible):
            explanations = tuple(
                item.explanation for item in trial.infeasible if scene_id in item.scene_ids
            )
            raise InfeasibleScheduleError(
                "manual move would silently break a hard constraint",
                explanations=explanations,
            )
        written = self._put(trial)
        self._audit(principal, acl_epoch, "schedule.move_scene", written.id, scene_id)
        return written

    def alternatives(
        self,
        schedule_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        seed: int,
    ) -> ScheduleScenario:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        packed = pack(
            stored.demands,
            seed=seed,
            pins={item.scene_id: item.board_index for item in stored.pins},
            blocked=tuple(
                (item.kind, item.name, item.board_index) for item in stored.availability
            ),
        )
        scenario = ScheduleScenario(
            id=new_id("scenario_model"),
            seed=seed,
            boards=self._boards(packed.placements),
            infeasible=packed.infeasible,
        )
        self._audit(principal, acl_epoch, "schedule.alternatives", stored.id, str(seed))
        return scenario

    def explain(
        self, schedule_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[Conflict, ...]:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        return stored.infeasible + stored.conflicts

    def export_boards(
        self, schedule_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if stored.labeled_stale or stored.projection.is_stale:
            raise StaleScheduleError("stale schedule cannot be exported as current")
        lines = [
            f"SCHEDULE {stored.id}",
            f"SEED {stored.seed}",
            f"REVISION {stored.projection.source_revision_id}",
        ]
        for board in stored.boards:
            lines.append(f"BOARD {board.index} minutes={board.used_minutes}")
            for strip in board.strips:
                lines.append(
                    f"  {strip.order}\t{strip.scene.scene_id}\t{strip.scene.location}\t"
                    f"{strip.scene.day_part.value}"
                )
        self._audit(principal, acl_epoch, "schedule.export", stored.id, str(stored.seed))
        return "\n".join(lines)

    def notify_breakdown_changed(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        index = load_index(self.workspace)
        schedule_ids = list(dict(index.get("by_breakdown", {})).get(breakdown_id, []))
        stale_ids: list[str] = []
        for schedule_id in schedule_ids:
            stored = self.get_schedule(schedule_id, principal=principal, acl_epoch=acl_epoch)
            if self.dependencies is not None and stored.config_node_id:
                self.dependencies.invalidate_inputs(
                    [stored.config_node_id],
                    principal=principal,
                    acl_epoch=acl_epoch,
                )
            marked = self._put(self._with_projection_stale(stored, stale=True))
            stale_ids.append(marked.id)
        self._audit(
            principal,
            acl_epoch,
            "schedule.notify_breakdown_changed",
            breakdown_id,
            ",".join(stale_ids),
        )
        return tuple(stale_ids)

    def _demands(
        self, stored: StoredBreakdown, durations: dict[str, int]
    ) -> tuple[SceneDemand, ...]:
        document = self.revisions.load_revision(stored.locked_revision_id)
        compiled = self.compiler.compile(document)
        stunt_scenes = self._scenes_for(stored.elements, ElementKind.STUNT)
        minor_scenes = self._scenes_for(stored.elements, ElementKind.MINOR)
        demands: list[SceneDemand] = []
        for scene in compiled.scenes:
            day_part = self._day_part(scene.time_of_day)
            duration = durations.get(scene.scene_id, DEFAULT_SCENE_MINUTES)
            demands.append(
                SceneDemand(
                    scene_id=scene.scene_id,
                    location=(scene.location or "UNSPECIFIED").strip() or "UNSPECIFIED",
                    day_part=day_part,
                    cast=tuple(sorted(name.casefold() for name in scene.character_names)),
                    duration_minutes=duration,
                    has_stunt=scene.scene_id in stunt_scenes,
                    has_minor=scene.scene_id in minor_scenes,
                    heading=scene.heading,
                )
            )
        return tuple(demands)

    def _scenes_for(
        self, elements: Sequence[BreakdownElement], kind: ElementKind
    ) -> set[str]:
        scenes: set[str] = set()
        for element in elements:
            if element.kind is not kind:
                continue
            for evidence in element.evidence:
                if evidence.scene_id:
                    scenes.add(evidence.scene_id)
        return scenes

    def _day_part(self, value: str | None) -> DayPart:
        if value is None:
            return DayPart.UNKNOWN
        lowered = value.casefold()
        if "night" in lowered:
            return DayPart.NIGHT
        if "day" in lowered:
            return DayPart.DAY
        return DayPart.UNKNOWN

    def _boards(self, placements: Sequence[Any]) -> tuple[Board, ...]:
        grouped: dict[int, list[Any]] = {}
        for item in placements:
            grouped.setdefault(item.board_index, []).append(item)
        boards: list[Board] = []
        for index in sorted(grouped):
            strips = tuple(
                Strip(
                    id=f"stp_{new_ulid()}",
                    board_index=item.board_index,
                    order=item.order,
                    scene=item.scene,
                    used_minutes=item.used_minutes,
                    company_move_minutes=item.company_move_minutes,
                    pinned=item.pinned,
                )
                for item in grouped[index]
            )
            boards.append(
                Board(
                    id=f"brd_{new_ulid()}",
                    index=index,
                    strips=strips,
                    used_minutes=strips[-1].used_minutes if strips else 0,
                )
            )
        return tuple(boards)

    def _repack(
        self,
        stored: StoredSchedule,
        *,
        pins: tuple[Pin, ...] | None = None,
        availability: tuple[AvailabilityBlock, ...] | None = None,
        durations: dict[str, int] | None = None,
        seed: int | None = None,
    ) -> StoredSchedule:
        next_pins = pins if pins is not None else stored.pins
        next_availability = availability if availability is not None else stored.availability
        next_durations = dict(stored.durations if durations is None else durations)
        next_seed = stored.seed if seed is None else seed
        demands = tuple(
            SceneDemand(
                scene_id=item.scene_id,
                location=item.location,
                day_part=item.day_part,
                cast=item.cast,
                duration_minutes=next_durations.get(item.scene_id, item.duration_minutes),
                has_stunt=item.has_stunt,
                has_minor=item.has_minor,
                heading=item.heading,
            )
            for item in stored.demands
        )
        packed = pack(
            demands,
            seed=next_seed,
            pins={item.scene_id: item.board_index for item in next_pins},
            blocked=tuple(
                (item.kind, item.name, item.board_index) for item in next_availability
            ),
        )
        payload = stored.projection.to_dict()
        data = dict(payload.get("data") or {})
        data["seed"] = next_seed
        data["board_count"] = len({item.board_index for item in packed.placements})
        payload["data"] = data
        payload["computed_at"] = self.clock()
        payload["is_stale"] = False
        return StoredSchedule(
            projection=ProductionProjection.from_dict(payload),
            breakdown_id=stored.breakdown_id,
            seed=next_seed,
            boards=self._boards(packed.placements),
            demands=demands,
            pins=next_pins,
            availability=next_availability,
            durations=next_durations,
            infeasible=packed.infeasible,
            conflicts=packed.conflicts,
            labeled_stale=False,
            config_node_id=stored.config_node_id,
            analysis_node_id=stored.analysis_node_id,
        )

    def _demand(self, stored: StoredSchedule, scene_id: str) -> SceneDemand:
        for item in stored.demands:
            if item.scene_id == scene_id:
                return item
        raise StripNotFoundError(f"scene {scene_id} is not on schedule {stored.id}")

    def _load(self, schedule_id: str) -> StoredSchedule:
        index = load_index(self.workspace)
        digest = dict(index.get("schedule_digests", {})).get(schedule_id)
        if digest is None:
            raise ScheduleNotFoundError(f"schedule {schedule_id} is not in the index")
        return StoredSchedule.from_dict(load_payload(self.workspace, str(digest)))

    def _put(self, stored: StoredSchedule) -> StoredSchedule:
        def persist(index: dict[str, Any]) -> StoredSchedule:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("schedule_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["schedule_ids"] = ids
            digests = dict(index.get("schedule_digests", {}))
            digests[stored.id] = digest
            index["schedule_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            by_breakdown = dict(index.get("by_breakdown", {}))
            breakdown_ids = list(by_breakdown.get(stored.breakdown_id, []))
            if stored.id not in breakdown_ids:
                breakdown_ids.append(stored.id)
            by_breakdown[stored.breakdown_id] = breakdown_ids
            index["by_breakdown"] = by_breakdown
            return stored

        return mutate_index(self.workspace, persist)

    def _attach_dependency_nodes(
        self,
        stored: StoredSchedule,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredSchedule:
        if self.dependencies is None:
            return stored
        config = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.CONFIGURATION,
            principal=principal,
            acl_epoch=acl_epoch,
            subject_id=stored.id,
        )
        analysis = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config.id,),
            subject_id=stored.id,
        )
        rewritten = StoredSchedule(
            projection=stored.projection,
            breakdown_id=stored.breakdown_id,
            seed=stored.seed,
            boards=stored.boards,
            demands=stored.demands,
            pins=stored.pins,
            availability=stored.availability,
            durations=stored.durations,
            infeasible=stored.infeasible,
            conflicts=stored.conflicts,
            labeled_stale=False,
            config_node_id=config.id,
            analysis_node_id=analysis.id,
        )
        return self._put(rewritten)

    def _with_freshness(
        self, stored: StoredSchedule, principal: Principal, acl_epoch: int
    ) -> StoredSchedule:
        labeled = stored.labeled_stale
        if self.dependencies is not None and stored.analysis_node_id:
            view = self.dependencies.view_node(
                stored.analysis_node_id, principal=principal, acl_epoch=acl_epoch
            )
            labeled = labeled or view.state is NodeState.STALE
        if labeled == stored.labeled_stale and stored.projection.is_stale == labeled:
            return stored
        return self._with_projection_stale(stored, stale=labeled)

    def _with_projection_stale(self, stored: StoredSchedule, *, stale: bool) -> StoredSchedule:
        payload = stored.projection.to_dict()
        payload["is_stale"] = stale
        return StoredSchedule(
            projection=ProductionProjection.from_dict(payload),
            breakdown_id=stored.breakdown_id,
            seed=stored.seed,
            boards=stored.boards,
            demands=stored.demands,
            pins=stored.pins,
            availability=stored.availability,
            durations=stored.durations,
            infeasible=stored.infeasible,
            conflicts=stored.conflicts,
            labeled_stale=stale,
            config_node_id=stored.config_node_id,
            analysis_node_id=stored.analysis_node_id,
        )

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
            object_kind="schedule",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
