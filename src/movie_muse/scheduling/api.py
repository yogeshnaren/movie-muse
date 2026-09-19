"""Public surface of ``movie_muse.scheduling``.

Hosts and other modules must import this module, never sibling internals.
Hard constraints never silently break. Breakdown changes stale affected schedules.
"""

from __future__ import annotations

from movie_muse.scheduling.engine import (
    COMPANY_MOVE_MINUTES,
    DAY_MINUTES,
    DEFAULT_SCENE_MINUTES,
)
from movie_muse.scheduling.errors import (
    InfeasibleScheduleError,
    ScheduleNotFoundError,
    SchedulingError,
    StaleScheduleError,
    StripNotFoundError,
)
from movie_muse.scheduling.service import ScheduleService
from movie_muse.scheduling.types import (
    AvailabilityBlock,
    Board,
    Conflict,
    ConstraintSeverity,
    DayPart,
    Pin,
    ResourceKind,
    SceneDemand,
    ScheduleScenario,
    StoredSchedule,
    Strip,
)

__all__ = [
    "COMPANY_MOVE_MINUTES",
    "DAY_MINUTES",
    "DEFAULT_SCENE_MINUTES",
    "AvailabilityBlock",
    "Board",
    "Conflict",
    "ConstraintSeverity",
    "DayPart",
    "InfeasibleScheduleError",
    "Pin",
    "ResourceKind",
    "SceneDemand",
    "ScheduleNotFoundError",
    "ScheduleScenario",
    "ScheduleService",
    "SchedulingError",
    "StaleScheduleError",
    "StoredSchedule",
    "Strip",
    "StripNotFoundError",
]
