"""Typed failures for department handoffs."""

from __future__ import annotations


class HandoffError(RuntimeError):
    """Base class for department-handoff failures."""


class DepartmentDeniedError(HandoffError):
    """The principal cannot view or act on this department."""


class PacketNotFoundError(HandoffError):
    """The named handoff packet is not in the index."""


class DecisionNotFoundError(HandoffError):
    """The named craft decision is not in the index."""


class NoticeNotFoundError(HandoffError):
    """The named change notice is not in the index."""


class AssignmentNotFoundError(HandoffError):
    """The named assignment is not in the index."""
