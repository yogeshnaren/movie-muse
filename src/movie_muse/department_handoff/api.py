"""Public surface of ``movie_muse.department_handoff``.

Hosts and other modules must import this module, never sibling internals.
Departments see permitted data only. Craft confirmations emit ProjectEvents.
"""

from __future__ import annotations

from movie_muse.department_handoff.errors import (
    AssignmentNotFoundError,
    DecisionNotFoundError,
    DepartmentDeniedError,
    HandoffError,
    NoticeNotFoundError,
    PacketNotFoundError,
)
from movie_muse.department_handoff.mapping import KIND_DEPARTMENT, department_for, kinds_for
from movie_muse.department_handoff.service import DepartmentHandoffService
from movie_muse.department_handoff.types import (
    Assignment,
    ChangeNotice,
    CraftAction,
    CraftDecision,
    DepartmentPacket,
    OperationalEvent,
)

__all__ = [
    "KIND_DEPARTMENT",
    "Assignment",
    "AssignmentNotFoundError",
    "ChangeNotice",
    "CraftAction",
    "CraftDecision",
    "DecisionNotFoundError",
    "DepartmentDeniedError",
    "DepartmentHandoffService",
    "DepartmentPacket",
    "HandoffError",
    "NoticeNotFoundError",
    "OperationalEvent",
    "PacketNotFoundError",
    "department_for",
    "kinds_for",
]
