"""Deterministic seeded packing. Hard constraints never place an invalid strip."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random

from movie_muse.scheduling.types import (
    Conflict,
    ConstraintSeverity,
    DayPart,
    ResourceKind,
    SceneDemand,
)

DAY_MINUTES = 720
COMPANY_MOVE_MINUTES = 60
DEFAULT_SCENE_MINUTES = 120


@dataclass
class _BoardState:
    index: int
    used: int = 0
    location: str | None = None
    has_night: bool = False
    has_stunt: bool = False
    has_minor: bool = False
    cast: set[str] = field(default_factory=set)
    night_cast: set[str] = field(default_factory=set)
    scene_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Placement:
    scene: SceneDemand
    board_index: int
    order: int
    used_minutes: int
    company_move_minutes: int
    pinned: bool


@dataclass(frozen=True, slots=True)
class PackResult:
    placements: tuple[Placement, ...]
    infeasible: tuple[Conflict, ...]
    conflicts: tuple[Conflict, ...]


def pack(
    demands: Sequence[SceneDemand],
    *,
    seed: int,
    pins: Mapping[str, int] | None = None,
    blocked: Sequence[tuple[ResourceKind, str, int]] = (),
) -> PackResult:
    rng = Random(seed)
    pins = dict(pins or {})
    blocked_cast: dict[str, set[int]] = {}
    blocked_location: dict[str, set[int]] = {}
    for kind, name, board_index in blocked:
        target = blocked_cast if kind is ResourceKind.CAST else blocked_location
        target.setdefault(name.casefold(), set()).add(board_index)

    remaining = {item.scene_id: item for item in demands}
    boards: list[_BoardState] = []
    placements: list[Placement] = []
    infeasible: list[Conflict] = []

    def ensure_board(index: int) -> _BoardState:
        while len(boards) < index:
            boards.append(_BoardState(index=len(boards) + 1))
        return boards[index - 1]

    for scene_id, board_index in sorted(pins.items(), key=lambda item: (item[1], item[0])):
        scene = remaining.pop(scene_id, None)
        if scene is None:
            continue
        board = ensure_board(board_index)
        reason = _hard_reason(board, scene, boards, blocked_cast, blocked_location)
        if reason is not None:
            infeasible.append(reason)
            continue
        placements.append(_place(board, scene, pinned=True))

    groups: dict[tuple[int, str], list[SceneDemand]] = {}
    for scene in remaining.values():
        groups.setdefault((_day_rank(scene.day_part), scene.location), []).append(scene)
    day_ranks = sorted({key[0] for key in groups})
    ordered: list[SceneDemand] = []
    for rank in day_ranks:
        locations = sorted({key[1] for key in groups if key[0] == rank})
        rng.shuffle(locations)
        for location in locations:
            members = sorted(
                groups[(rank, location)],
                key=lambda item: item.scene_id,
            )
            ordered.extend(members)

    for scene in ordered:
        if scene.has_stunt and scene.has_minor:
            infeasible.append(
                Conflict(
                    severity=ConstraintSeverity.HARD,
                    code="safety_stunt_minor",
                    scene_ids=(scene.scene_id,),
                    explanation=(
                        f"scene {scene.scene_id} combines a stunt and a minor and "
                        "cannot be placed without breaking a hard safety constraint"
                    ),
                )
            )
            continue
        placed = False
        extras = [
            _BoardState(index=len(boards) + 1),
            _BoardState(index=len(boards) + 2),
        ]
        for board in list(boards) + extras:
            reason = _hard_reason(board, scene, boards, blocked_cast, blocked_location)
            if reason is not None:
                continue
            if board.index > len(boards):
                boards.append(board)
            placements.append(_place(board, scene, pinned=False))
            placed = True
            break
        if not placed:
            infeasible.append(
                Conflict(
                    severity=ConstraintSeverity.HARD,
                    code="no_feasible_board",
                    scene_ids=(scene.scene_id,),
                    explanation=(
                        f"scene {scene.scene_id} has no board that satisfies availability, "
                        "labor/rest, safety, day/night, company-move, and day-capacity constraints"
                    ),
                )
            )

    soft: list[Conflict] = []
    script_ids = [item.scene_id for item in demands]
    placed_ids = [item.scene.scene_id for item in sorted(placements, key=_placement_key)]
    if placed_ids and placed_ids != [item for item in script_ids if item in set(placed_ids)]:
        soft.append(
            Conflict(
                severity=ConstraintSeverity.SOFT,
                code="script_order",
                scene_ids=tuple(placed_ids),
                explanation="shooting order differs from screenplay order to honor constraints",
            )
        )
    return PackResult(
        placements=tuple(sorted(placements, key=_placement_key)),
        infeasible=tuple(infeasible),
        conflicts=tuple(soft),
    )


def join_conflict(
    scene: SceneDemand,
    occupants: Sequence[SceneDemand],
    *,
    board_index: int,
    previous_night_cast: Sequence[str] = (),
    blocked: Sequence[tuple[ResourceKind, str, int]] = (),
) -> Conflict | None:
    """Return the hard-constraint conflict of adding ``scene`` to existing occupants."""

    blocked_cast: dict[str, set[int]] = {}
    blocked_location: dict[str, set[int]] = {}
    for kind, name, index in blocked:
        target = blocked_cast if kind is ResourceKind.CAST else blocked_location
        target.setdefault(name.casefold(), set()).add(index)
    board = _BoardState(index=board_index)
    previous: list[_BoardState] = []
    if previous_night_cast:
        prior = _BoardState(index=board_index - 1)
        prior.night_cast.update(previous_night_cast)
        previous.append(prior)
    for occupant in occupants:
        reason = _hard_reason(board, occupant, previous, blocked_cast, blocked_location)
        if reason is not None:
            return reason
        _place(board, occupant, pinned=False)
    return _hard_reason(board, scene, previous, blocked_cast, blocked_location)


def _placement_key(item: Placement) -> tuple[int, int, str]:
    return (item.board_index, item.order, item.scene.scene_id)


def _day_rank(part: DayPart) -> int:
    if part is DayPart.DAY:
        return 0
    if part is DayPart.UNKNOWN:
        return 1
    return 2


def _place(board: _BoardState, scene: SceneDemand, *, pinned: bool) -> Placement:
    move = 0
    if board.location is not None and board.location != scene.location:
        move = COMPANY_MOVE_MINUTES
    board.used += move + scene.duration_minutes
    board.location = scene.location
    board.has_night = board.has_night or scene.day_part is DayPart.NIGHT
    board.has_stunt = board.has_stunt or scene.has_stunt
    board.has_minor = board.has_minor or scene.has_minor
    board.cast.update(scene.cast)
    if scene.day_part is DayPart.NIGHT:
        board.night_cast.update(scene.cast)
    order = len(board.scene_ids)
    board.scene_ids.append(scene.scene_id)
    return Placement(
        scene=scene,
        board_index=board.index,
        order=order,
        used_minutes=board.used,
        company_move_minutes=move,
        pinned=pinned,
    )


def _hard_reason(
    board: _BoardState,
    scene: SceneDemand,
    boards: Sequence[_BoardState],
    blocked_cast: Mapping[str, set[int]],
    blocked_location: Mapping[str, set[int]],
) -> Conflict | None:
    if scene.has_stunt and scene.has_minor:
        return Conflict(
            severity=ConstraintSeverity.HARD,
            code="safety_stunt_minor",
            scene_ids=(scene.scene_id,),
            explanation=(
                f"scene {scene.scene_id} combines a stunt and a minor on one strip"
            ),
        )
    if scene.has_stunt and board.has_minor or scene.has_minor and board.has_stunt:
        return Conflict(
            severity=ConstraintSeverity.HARD,
            code="safety_stunt_minor",
            scene_ids=(scene.scene_id, *board.scene_ids),
            explanation=(
                f"board {board.index} would combine stunt work and a minor; "
                "hard safety constraint refuses the placement"
            ),
        )
    if board.has_night and scene.day_part is DayPart.DAY:
        return Conflict(
            severity=ConstraintSeverity.HARD,
            code="day_after_night",
            scene_ids=(scene.scene_id, *board.scene_ids),
            explanation=(
                f"board {board.index} already has night work; a day scene cannot follow"
            ),
        )
    move = (
        COMPANY_MOVE_MINUTES
        if board.location is not None and board.location != scene.location
        else 0
    )
    if board.used + move + scene.duration_minutes > DAY_MINUTES:
        return Conflict(
            severity=ConstraintSeverity.HARD,
            code="day_capacity",
            scene_ids=(scene.scene_id, *board.scene_ids),
            explanation=(
                f"board {board.index} lacks remaining minutes for a {move}-minute company "
                f"move plus {scene.duration_minutes} minutes of {scene.scene_id}"
            ),
        )
    for name in scene.cast:
        if board.index in blocked_cast.get(name.casefold(), set()):
            return Conflict(
                severity=ConstraintSeverity.HARD,
                code="cast_unavailable",
                scene_ids=(scene.scene_id,),
                explanation=(
                    f"{name} is unavailable on board {board.index}; "
                    "hard availability constraint refuses the placement"
                ),
            )
    if board.index in blocked_location.get(scene.location.casefold(), set()):
        return Conflict(
            severity=ConstraintSeverity.HARD,
            code="location_unavailable",
            scene_ids=(scene.scene_id,),
            explanation=(
                f"location {scene.location} is unavailable on board {board.index}"
            ),
        )
    previous = next((item for item in boards if item.index == board.index - 1), None)
    if previous is not None:
        overlap = previous.night_cast.intersection(scene.cast)
        if overlap and scene.day_part is DayPart.DAY:
            names = ", ".join(sorted(overlap))
            return Conflict(
                severity=ConstraintSeverity.HARD,
                code="labor_rest",
                scene_ids=(scene.scene_id, *previous.scene_ids),
                explanation=(
                    f"{names} worked night on board {previous.index}; "
                    f"turnaround forbids day work on board {board.index}"
                ),
            )
    return None
