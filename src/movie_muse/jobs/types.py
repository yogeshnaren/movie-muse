"""Durable queue, delivery, and trace domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    DEAD_LETTER = "dead_letter"
    CANCELED = "canceled"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"


@dataclass(frozen=True, slots=True)
class JobFailure:
    code: str
    message: str
    retryable: bool
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobFailure:
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            retryable=bool(data["retryable"]),
            recorded_at=str(data["recorded_at"]),
        )


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    job_type: str
    payload_digest: str
    actor_id: str
    project_id: str
    idempotency_key: str
    priority: int
    cost_budget: float
    timeout_seconds: int
    max_attempts: int
    input_fingerprint: str
    acl_epoch: int
    permission_snapshot_id: str
    trace_id: str
    status: JobStatus
    created_at: str
    available_at: str
    attempt_count: int = 0
    worker_id: str | None = None
    leased_at: str | None = None
    lease_expires_at: str | None = None
    heartbeat_at: str | None = None
    progress: float = 0.0
    result_digest: str | None = None
    provider_delivery_id: str | None = None
    actual_cost: float = 0.0
    failure: JobFailure | None = None
    completed_at: str | None = None
    canceled_at: str | None = None
    canceled_by: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {
            JobStatus.COMPLETED,
            JobStatus.DEAD_LETTER,
            JobStatus.CANCELED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "payload_digest": self.payload_digest,
            "actor_id": self.actor_id,
            "project_id": self.project_id,
            "idempotency_key": self.idempotency_key,
            "priority": self.priority,
            "cost_budget": self.cost_budget,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "input_fingerprint": self.input_fingerprint,
            "acl_epoch": self.acl_epoch,
            "permission_snapshot_id": self.permission_snapshot_id,
            "trace_id": self.trace_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "available_at": self.available_at,
            "attempt_count": self.attempt_count,
            "worker_id": self.worker_id,
            "leased_at": self.leased_at,
            "lease_expires_at": self.lease_expires_at,
            "heartbeat_at": self.heartbeat_at,
            "progress": self.progress,
            "result_digest": self.result_digest,
            "provider_delivery_id": self.provider_delivery_id,
            "actual_cost": self.actual_cost,
            "failure": self.failure.to_dict() if self.failure else None,
            "completed_at": self.completed_at,
            "canceled_at": self.canceled_at,
            "canceled_by": self.canceled_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        failure = data.get("failure")
        return cls(
            id=str(data["id"]),
            job_type=str(data["job_type"]),
            payload_digest=str(data["payload_digest"]),
            actor_id=str(data["actor_id"]),
            project_id=str(data["project_id"]),
            idempotency_key=str(data["idempotency_key"]),
            priority=int(data["priority"]),
            cost_budget=float(data["cost_budget"]),
            timeout_seconds=int(data["timeout_seconds"]),
            max_attempts=int(data["max_attempts"]),
            input_fingerprint=str(data["input_fingerprint"]),
            acl_epoch=int(data["acl_epoch"]),
            permission_snapshot_id=str(data["permission_snapshot_id"]),
            trace_id=str(data["trace_id"]),
            status=JobStatus(str(data["status"])),
            created_at=str(data["created_at"]),
            available_at=str(data["available_at"]),
            attempt_count=int(data.get("attempt_count", 0)),
            worker_id=str(data["worker_id"]) if data.get("worker_id") else None,
            leased_at=str(data["leased_at"]) if data.get("leased_at") else None,
            lease_expires_at=(
                str(data["lease_expires_at"]) if data.get("lease_expires_at") else None
            ),
            heartbeat_at=str(data["heartbeat_at"]) if data.get("heartbeat_at") else None,
            progress=float(data.get("progress", 0.0)),
            result_digest=str(data["result_digest"]) if data.get("result_digest") else None,
            provider_delivery_id=(
                str(data["provider_delivery_id"])
                if data.get("provider_delivery_id")
                else None
            ),
            actual_cost=float(data.get("actual_cost", 0.0)),
            failure=JobFailure.from_dict(failure) if isinstance(failure, dict) else None,
            completed_at=str(data["completed_at"]) if data.get("completed_at") else None,
            canceled_at=str(data["canceled_at"]) if data.get("canceled_at") else None,
            canceled_by=str(data["canceled_by"]) if data.get("canceled_by") else None,
        )


@dataclass(frozen=True, slots=True)
class OutboxIntent:
    id: str
    job_id: str
    idempotency_key: str
    payload_digest: str
    trace_id: str
    status: OutboxStatus
    created_at: str
    delivered_at: str | None = None
    delivery_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "idempotency_key": self.idempotency_key,
            "payload_digest": self.payload_digest,
            "trace_id": self.trace_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "delivery_count": self.delivery_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutboxIntent:
        return cls(
            id=str(data["id"]),
            job_id=str(data["job_id"]),
            idempotency_key=str(data["idempotency_key"]),
            payload_digest=str(data["payload_digest"]),
            trace_id=str(data["trace_id"]),
            status=OutboxStatus(str(data["status"])),
            created_at=str(data["created_at"]),
            delivered_at=str(data["delivered_at"]) if data.get("delivered_at") else None,
            delivery_count=int(data.get("delivery_count", 0)),
        )


@dataclass(frozen=True, slots=True)
class InboxReceipt:
    delivery_id: str
    job_id: str
    response_digest: str
    actual_cost: float
    trace_id: str
    received_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "job_id": self.job_id,
            "response_digest": self.response_digest,
            "actual_cost": self.actual_cost,
            "trace_id": self.trace_id,
            "received_at": self.received_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InboxReceipt:
        return cls(
            delivery_id=str(data["delivery_id"]),
            job_id=str(data["job_id"]),
            response_digest=str(data["response_digest"]),
            actual_cost=float(data["actual_cost"]),
            trace_id=str(data["trace_id"]),
            received_at=str(data["received_at"]),
        )


@dataclass(frozen=True, slots=True)
class TraceEvent:
    job_id: str
    trace_id: str
    event: str
    recorded_at: str
    worker_id: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "event": self.event,
            "recorded_at": self.recorded_at,
            "worker_id": self.worker_id,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        return cls(
            job_id=str(data["job_id"]),
            trace_id=str(data["trace_id"]),
            event=str(data["event"]),
            recorded_at=str(data["recorded_at"]),
            worker_id=str(data["worker_id"]) if data.get("worker_id") else None,
            detail=str(data["detail"]) if data.get("detail") else None,
        )
