"""Durable worker process adapter over the jobs public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from movie_muse.jobs.api import InboxReceipt, Job, JobService


class WorkerRuntime:
    """Names a worker lease owner and records every transition through JobService."""

    def __init__(self, jobs: JobService, *, worker_id: str, lease_seconds: int = 30) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.jobs = jobs
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def lease(self, *, now: datetime) -> Job | None:
        return self.jobs.lease(
            self.worker_id,
            now=now,
            lease_seconds=self.lease_seconds,
        )

    def heartbeat(self, job_id: str, *, progress: float) -> Job:
        return self.jobs.heartbeat(job_id, self.worker_id, progress=progress)

    def complete(self, job_id: str, result: dict[str, Any]) -> Job:
        return self.jobs.complete(job_id, self.worker_id, result)

    def fail(self, job_id: str, error: str | Exception, *, retryable: bool) -> Job:
        return self.jobs.fail(job_id, self.worker_id, error, retryable)

    def record_provider_response(
        self,
        job_id: str,
        *,
        delivery_id: str,
        response: dict[str, Any],
        actual_cost: float = 0.0,
    ) -> InboxReceipt:
        return self.jobs.record_provider_response(
            job_id,
            self.worker_id,
            delivery_id=delivery_id,
            response=response,
            actual_cost=actual_cost,
        )

    def persist_provider_result(self, job_id: str, *, delivery_id: str) -> Job:
        return self.jobs.persist_provider_result(
            job_id,
            self.worker_id,
            delivery_id=delivery_id,
        )

    def recover_pending_outbox(self) -> int:
        return self.jobs.replay_pending_outbox()
