"""Typed failures for durable job operations."""

from __future__ import annotations


class JobError(RuntimeError):
    """Base class for fail-closed job infrastructure errors."""


class JobNotFoundError(JobError):
    """The requested durable job does not exist."""


class InvalidJobStateError(JobError):
    """The requested operation is invalid for the job's durable state."""


class LeaseOwnershipError(JobError):
    """A worker attempted to mutate a lease it does not own."""


class WorkerCommitDeniedError(JobError):
    """A worker result failed authorization, freshness, or quota checks."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"worker commit denied ({reason})")
        self.reason = reason
