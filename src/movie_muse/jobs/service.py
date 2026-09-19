"""Durable job authority backed by a content-addressed jobs-owned index."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthContext,
    AuthorizationService,
    ResourceKind,
    parse_action,
    parse_resource_kind,
)
from movie_muse.identity.api import IdentityService
from movie_muse.jobs.errors import (
    InvalidJobStateError,
    JobNotFoundError,
    LeaseOwnershipError,
    WorkerCommitDeniedError,
)
from movie_muse.jobs.storage import load_index, load_payload, mutate_index, put_payload
from movie_muse.jobs.types import (
    InboxReceipt,
    Job,
    JobFailure,
    JobStatus,
    OutboxIntent,
    OutboxStatus,
    TraceEvent,
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.schemas.api import new_ulid


class InputFingerprintResolver(Protocol):
    """Recompute the current input identity for a durable job."""

    def __call__(self, job: Job) -> str: ...


Clock = Callable[[], datetime]


def _system_clock() -> datetime:
    return datetime.now(tz=UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _stamp(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class JobService:
    """Queue, delivery, authorization, freshness, and once-only commit authority."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        identity: IdentityService,
        authorization: AuthorizationService,
        audit: AuditLog,
        input_fingerprint_resolver: InputFingerprintResolver,
        *,
        clock: Clock = _system_clock,
    ) -> None:
        self.workspace = workspace
        self.identity = identity
        self.authorization = authorization
        self.audit = audit
        self.input_fingerprint_resolver = input_fingerprint_resolver
        self.clock = clock

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        actor_id: str,
        project_id: str,
        idempotency_key: str,
        priority: int,
        cost_budget: float,
        timeout_seconds: int,
        max_attempts: int,
        input_fingerprint: str,
        acl_epoch: int,
        permission_snapshot_id: str,
        trace_id: str,
    ) -> Job:
        self._validate_enqueue(
            job_type=job_type,
            actor_id=actor_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            cost_budget=cost_budget,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            input_fingerprint=input_fingerprint,
            permission_snapshot_id=permission_snapshot_id,
            trace_id=trace_id,
        )
        payload_digest = put_payload(self.workspace, payload)
        now = _stamp(self.clock())
        estimated_cost = self._cost(payload.get("estimated_cost", 0.0), "estimated_cost")

        def mutate(index: dict[str, Any]) -> Job:
            existing_id = index["idempotency"].get(idempotency_key)
            if existing_id is not None:
                return Job.from_dict(index["jobs"][str(existing_id)])
            status = JobStatus.QUEUED
            failure: JobFailure | None = None
            if estimated_cost > cost_budget:
                status = JobStatus.DEAD_LETTER
                failure = JobFailure(
                    code="cost_budget_exceeded",
                    message="estimated cost exceeds job budget",
                    retryable=False,
                    recorded_at=now,
                )
            job = Job(
                id=f"job_{new_ulid()}",
                job_type=job_type,
                payload_digest=payload_digest,
                actor_id=actor_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                priority=priority,
                cost_budget=cost_budget,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                input_fingerprint=input_fingerprint,
                acl_epoch=acl_epoch,
                permission_snapshot_id=permission_snapshot_id,
                trace_id=trace_id,
                status=status,
                created_at=now,
                available_at=now,
                failure=failure,
            )
            index["jobs"][job.id] = job.to_dict()
            index["job_order"].append(job.id)
            index["idempotency"][idempotency_key] = job.id
            self._trace(index, job, "enqueued", recorded_at=now)
            if failure is not None:
                self._trace(
                    index,
                    job,
                    "dead_lettered",
                    recorded_at=now,
                    detail=failure.code,
                )
            return job

        return mutate_index(self.workspace, mutate)

    def get(self, job_id: str) -> Job:
        raw = load_index(self.workspace)["jobs"].get(job_id)
        if raw is None:
            raise JobNotFoundError(f"unknown job: {job_id}")
        return Job.from_dict(raw)

    def payload(self, job_id: str) -> dict[str, Any]:
        payload = load_payload(self.workspace, self.get(job_id).payload_digest)
        if not isinstance(payload, dict):
            raise InvalidJobStateError("job payload is not an object")
        return cast(dict[str, Any], payload)

    def result(self, job_id: str) -> object | None:
        job = self.get(job_id)
        return None if job.result_digest is None else load_payload(self.workspace, job.result_digest)

    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_seconds: int,
    ) -> Job | None:
        if not worker_id or lease_seconds <= 0:
            raise ValueError("worker_id is required and lease_seconds must be positive")
        current = _as_utc(now)
        self.expire_stale_leases(now=current)
        current_stamp = _stamp(current)

        def mutate(index: dict[str, Any]) -> Job | None:
            candidates = []
            for job_id in index["job_order"]:
                job = Job.from_dict(index["jobs"][job_id])
                if job.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
                    continue
                if _parse(job.available_at) > current:
                    continue
                candidates.append(job)
            if not candidates:
                return None
            selected = min(
                candidates,
                key=lambda job: (
                    -job.priority,
                    index["job_order"].index(job.id),
                ),
            )
            expiry = current + timedelta(
                seconds=min(lease_seconds, selected.timeout_seconds)
            )
            leased = replace(
                selected,
                status=JobStatus.LEASED,
                worker_id=worker_id,
                leased_at=current_stamp,
                heartbeat_at=current_stamp,
                lease_expires_at=_stamp(expiry),
            )
            index["jobs"][leased.id] = leased.to_dict()
            self._trace(
                index,
                leased,
                "leased",
                worker_id=worker_id,
                recorded_at=current_stamp,
            )
            return leased

        return mutate_index(self.workspace, mutate)

    def heartbeat(self, job_id: str, worker_id: str, *, progress: float) -> Job:
        if not 0.0 <= progress <= 1.0:
            raise ValueError("progress must be between 0 and 1")
        now = _as_utc(self.clock())
        now_stamp = _stamp(now)

        def mutate(index: dict[str, Any]) -> Job:
            job = self._job_from(index, job_id)
            self._require_lease(job, worker_id, now=now)
            assert job.leased_at is not None
            assert job.lease_expires_at is not None
            original_duration = _parse(job.lease_expires_at) - _parse(job.leased_at)
            timeout_deadline = _parse(job.leased_at) + timedelta(seconds=job.timeout_seconds)
            extension = min(now + original_duration, timeout_deadline)
            updated = replace(
                job,
                heartbeat_at=now_stamp,
                lease_expires_at=_stamp(extension),
                progress=progress,
            )
            index["jobs"][job_id] = updated.to_dict()
            self._trace(
                index,
                updated,
                "heartbeat",
                worker_id=worker_id,
                recorded_at=now_stamp,
            )
            return updated

        return mutate_index(self.workspace, mutate)

    def expire_stale_leases(self, *, now: datetime | None = None) -> tuple[Job, ...]:
        current = _as_utc(now or self.clock())
        current_stamp = _stamp(current)

        def mutate(index: dict[str, Any]) -> tuple[Job, ...]:
            expired: list[Job] = []
            for job_id in list(index["job_order"]):
                job = Job.from_dict(index["jobs"][job_id])
                if (
                    job.status is not JobStatus.LEASED
                    or job.lease_expires_at is None
                    or _parse(job.lease_expires_at) > current
                ):
                    continue
                updated = self._retry_or_dead_letter(
                    job,
                    failure=JobFailure(
                        code="lease_timeout",
                        message="worker lease expired before completion",
                        retryable=True,
                        recorded_at=current_stamp,
                    ),
                    now=current,
                    immediate=True,
                )
                index["jobs"][job_id] = updated.to_dict()
                self._trace(
                    index,
                    updated,
                    (
                        "dead_lettered"
                        if updated.status is JobStatus.DEAD_LETTER
                        else "lease_expired"
                    ),
                    worker_id=job.worker_id,
                    recorded_at=current_stamp,
                    detail="lease_timeout",
                )
                expired.append(updated)
            return tuple(expired)

        return mutate_index(self.workspace, mutate)

    def complete(self, job_id: str, worker_id: str, result: dict[str, Any]) -> Job:
        return self._complete_guarded(job_id, worker_id, result, provider_delivery_id=None)

    def fail(
        self,
        job_id: str,
        worker_id: str,
        error: str | Exception,
        retryable: bool,
    ) -> Job:
        now = _as_utc(self.clock())
        now_stamp = _stamp(now)
        message = self._safe_error_message(error)
        code = self._error_code(error)

        def mutate(index: dict[str, Any]) -> Job:
            job = self._job_from(index, job_id)
            self._require_lease(job, worker_id, now=now)
            updated = self._retry_or_dead_letter(
                job,
                failure=JobFailure(
                    code=code,
                    message=message,
                    retryable=retryable,
                    recorded_at=now_stamp,
                ),
                now=now,
            )
            index["jobs"][job_id] = updated.to_dict()
            self._trace(
                index,
                updated,
                "failed" if updated.status is JobStatus.RETRY_WAIT else "dead_lettered",
                worker_id=worker_id,
                recorded_at=now_stamp,
                detail=code,
            )
            return updated

        return mutate_index(self.workspace, mutate)

    def cancel(self, job_id: str, actor_id: str) -> Job:
        now = _stamp(self.clock())

        def mutate(index: dict[str, Any]) -> Job:
            job = self._job_from(index, job_id)
            if job.status is JobStatus.COMPLETED:
                raise InvalidJobStateError("completed jobs cannot be canceled")
            if job.status is JobStatus.CANCELED:
                return job
            owner_id = self.identity.project_binding(job.project_id)["owner_actor_id"]
            if actor_id not in {job.actor_id, owner_id}:
                raise InvalidJobStateError("only the acting principal or project owner may cancel")
            canceled = replace(
                job,
                status=JobStatus.CANCELED,
                worker_id=None,
                lease_expires_at=None,
                canceled_at=now,
                canceled_by=actor_id,
            )
            index["jobs"][job_id] = canceled.to_dict()
            self._trace(index, canceled, "canceled", recorded_at=now)
            return canceled

        return mutate_index(self.workspace, mutate)

    def record_provider_response(
        self,
        job_id: str,
        worker_id: str,
        *,
        delivery_id: str,
        response: dict[str, Any],
        actual_cost: float = 0.0,
    ) -> InboxReceipt:
        if not delivery_id:
            raise ValueError("delivery_id is required")
        cost = self._cost(actual_cost, "actual_cost")
        digest = put_payload(self.workspace, response)
        now_dt = _as_utc(self.clock())
        now = _stamp(now_dt)

        def mutate(index: dict[str, Any]) -> InboxReceipt:
            existing = index["inbox"].get(delivery_id)
            if existing is not None:
                receipt = InboxReceipt.from_dict(existing)
                if receipt.job_id != job_id or receipt.response_digest != digest:
                    raise InvalidJobStateError("provider delivery id collision")
                return receipt
            job = self._job_from(index, job_id)
            self._require_lease(job, worker_id, now=now_dt)
            receipt = InboxReceipt(
                delivery_id=delivery_id,
                job_id=job_id,
                response_digest=digest,
                actual_cost=cost,
                trace_id=job.trace_id,
                received_at=now,
            )
            index["inbox"][delivery_id] = receipt.to_dict()
            updated = replace(
                job,
                provider_delivery_id=delivery_id,
                actual_cost=cost,
            )
            if cost > job.cost_budget:
                updated = self._dead_letter(
                    updated,
                    JobFailure(
                        code="cost_budget_exceeded",
                        message="actual provider cost exceeds job budget",
                        retryable=False,
                        recorded_at=now,
                    ),
                )
            index["jobs"][job_id] = updated.to_dict()
            self._trace(
                index,
                updated,
                (
                    "dead_lettered"
                    if updated.status is JobStatus.DEAD_LETTER
                    else "provider_response_recorded"
                ),
                worker_id=worker_id,
                recorded_at=now,
                detail=(
                    "cost_budget_exceeded"
                    if updated.status is JobStatus.DEAD_LETTER
                    else "provider_response"
                ),
            )
            return receipt

        receipt = mutate_index(self.workspace, mutate)
        if cost > self.get(job_id).cost_budget:
            raise WorkerCommitDeniedError("cost_budget_exceeded")
        return receipt

    def persist_provider_result(
        self,
        job_id: str,
        worker_id: str,
        *,
        delivery_id: str,
    ) -> Job:
        raw = load_index(self.workspace)["inbox"].get(delivery_id)
        if raw is None:
            raise InvalidJobStateError(f"unknown provider delivery: {delivery_id}")
        receipt = InboxReceipt.from_dict(raw)
        if receipt.job_id != job_id:
            raise InvalidJobStateError("provider delivery belongs to another job")
        result = load_payload(self.workspace, receipt.response_digest)
        if not isinstance(result, dict):
            raise InvalidJobStateError("provider response is not an object")
        return self._complete_guarded(
            job_id,
            worker_id,
            cast(dict[str, Any], result),
            provider_delivery_id=delivery_id,
            actual_cost=receipt.actual_cost,
        )

    def replay_outbox(self, intent_id: str) -> bool:
        """Apply a jobs-owned canonical mutation once, even under replay."""

        now = _stamp(self.clock())

        def mutate(index: dict[str, Any]) -> bool:
            raw = index["outbox"].get(intent_id)
            if raw is None:
                raise InvalidJobStateError(f"unknown outbox intent: {intent_id}")
            intent = OutboxIntent.from_dict(raw)
            existing = index["canonical_mutations"].get(intent.idempotency_key)
            if existing is not None:
                if str(existing) != intent.payload_digest:
                    raise InvalidJobStateError("idempotency key already applied to another result")
                if intent.status is not OutboxStatus.DELIVERED:
                    index["outbox"][intent_id] = replace(
                        intent,
                        status=OutboxStatus.DELIVERED,
                        delivered_at=now,
                        delivery_count=1,
                    ).to_dict()
                return False
            index["canonical_mutations"][intent.idempotency_key] = intent.payload_digest
            index["outbox"][intent_id] = replace(
                intent,
                status=OutboxStatus.DELIVERED,
                delivered_at=now,
                delivery_count=1,
            ).to_dict()
            return True

        return mutate_index(self.workspace, mutate)

    def replay_pending_outbox(self) -> int:
        pending = [
            OutboxIntent.from_dict(raw).id
            for raw in load_index(self.workspace)["outbox"].values()
            if OutboxIntent.from_dict(raw).status is OutboxStatus.PENDING
        ]
        return sum(1 for intent_id in pending if self.replay_outbox(intent_id))

    def canonical_result(self, idempotency_key: str) -> object | None:
        digest = load_index(self.workspace)["canonical_mutations"].get(idempotency_key)
        return None if digest is None else load_payload(self.workspace, str(digest))

    def applied_mutation_count(self, idempotency_key: str) -> int:
        return int(idempotency_key in load_index(self.workspace)["canonical_mutations"])

    def list_outbox(self) -> tuple[OutboxIntent, ...]:
        intents = [
            OutboxIntent.from_dict(raw) for raw in load_index(self.workspace)["outbox"].values()
        ]
        return tuple(sorted(intents, key=lambda item: (item.created_at, item.id)))

    def trace_events(self, job_id: str | None = None) -> tuple[TraceEvent, ...]:
        events = [
            TraceEvent.from_dict(raw) for raw in load_index(self.workspace)["trace_events"]
        ]
        if job_id is not None:
            events = [event for event in events if event.job_id == job_id]
        return tuple(events)

    def _complete_guarded(
        self,
        job_id: str,
        worker_id: str,
        result: dict[str, Any],
        *,
        provider_delivery_id: str | None,
        actual_cost: float | None = None,
    ) -> Job:
        job = self.get(job_id)
        if job.status is JobStatus.COMPLETED:
            return job
        now_dt = _as_utc(self.clock())
        self._require_lease(job, worker_id, now=now_dt)
        payload = self.payload(job_id)
        action, resource_kind, resource_id, department, protected = self._authorization_target(
            job, payload
        )
        principal = self.identity.principal(job.actor_id)
        resource = self.authorization.resource_for_project(
            job.project_id,
            kind=resource_kind,
            resource_id=resource_id,
            department=department,
            protected=protected,
        )
        decision = self.authorization.authorize(
            principal,
            action,
            resource,
            acl_epoch=job.acl_epoch,
            context=AuthContext(
                snapshot_id=job.permission_snapshot_id,
                correlation_id=job.trace_id,
            ),
        )
        if decision.denied:
            self._audit_worker_commit(job, PolicyDecision.DENY, decision.reason)
            self._reject_commit(
                job_id,
                worker_id,
                reason=decision.reason,
                retryable=False,
            )
            raise WorkerCommitDeniedError(decision.reason)
        current_fingerprint = self.input_fingerprint_resolver(job)
        if current_fingerprint != job.input_fingerprint:
            self._audit_worker_commit(job, PolicyDecision.DENY, "stale_input_fingerprint")
            self._reject_commit(
                job_id,
                worker_id,
                reason="stale_input_fingerprint",
                retryable=True,
            )
            raise WorkerCommitDeniedError("stale_input_fingerprint")
        cost = self._cost(
            actual_cost if actual_cost is not None else result.get("actual_cost", job.actual_cost),
            "actual_cost",
        )
        if cost > job.cost_budget:
            self._audit_worker_commit(job, PolicyDecision.DENY, "cost_budget_exceeded")
            self._reject_commit(
                job_id,
                worker_id,
                reason="cost_budget_exceeded",
                retryable=False,
            )
            raise WorkerCommitDeniedError("cost_budget_exceeded")
        self._audit_worker_commit(job, PolicyDecision.ALLOW, "authorized_current_inputs")
        result_digest = put_payload(self.workspace, result)
        now = _stamp(now_dt)

        def mutate(index: dict[str, Any]) -> tuple[Job, str]:
            current = self._job_from(index, job_id)
            if current.status is JobStatus.COMPLETED:
                assert current.result_digest is not None
                return current, f"outbox_{current.id}"
            self._require_lease(current, worker_id, now=now_dt)
            intent_id = f"outbox_{current.id}"
            existing_mutation = index["canonical_mutations"].get(current.idempotency_key)
            if existing_mutation is not None and str(existing_mutation) != result_digest:
                raise InvalidJobStateError("idempotency key already committed another result")
            completed = replace(
                current,
                status=JobStatus.COMPLETED,
                worker_id=None,
                lease_expires_at=None,
                heartbeat_at=now,
                progress=1.0,
                result_digest=result_digest,
                provider_delivery_id=provider_delivery_id or current.provider_delivery_id,
                actual_cost=cost,
                failure=None,
                completed_at=now,
            )
            intent = OutboxIntent(
                id=intent_id,
                job_id=current.id,
                idempotency_key=current.idempotency_key,
                payload_digest=result_digest,
                trace_id=current.trace_id,
                status=OutboxStatus.PENDING,
                created_at=now,
            )
            index["jobs"][job_id] = completed.to_dict()
            index["outbox"][intent_id] = intent.to_dict()
            self._trace(
                index,
                completed,
                "completed",
                worker_id=worker_id,
                recorded_at=now,
            )
            return completed, intent_id

        completed, intent_id = mutate_index(self.workspace, mutate)
        self.replay_outbox(intent_id)
        return completed

    def _reject_commit(
        self,
        job_id: str,
        worker_id: str,
        *,
        reason: str,
        retryable: bool,
    ) -> Job:
        message = self._failure_message(reason)
        return self.fail(
            job_id,
            worker_id,
            f"{reason}: {message}",
            retryable=retryable,
        )

    def _audit_worker_commit(
        self,
        job: Job,
        decision: PolicyDecision,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=job.actor_id,
            effective_principal_id=job.actor_id,
            operation="worker_commit",
            object_kind="job",
            object_id=job.id,
            policy_decision=decision,
            acl_epoch=job.acl_epoch,
            reason=reason,
            correlation_id=job.trace_id,
        )

    @staticmethod
    def _authorization_target(
        job: Job,
        payload: dict[str, Any],
    ) -> tuple[Action, ResourceKind, str, str | None, bool]:
        raw = payload.get("authorization", {})
        config = raw if isinstance(raw, dict) else {}
        action = parse_action(str(config.get("action", Action.PROPOSE.value)))
        kind = parse_resource_kind(str(config.get("resource_kind", ResourceKind.PROJECT.value)))
        if action is None:
            raise WorkerCommitDeniedError("unknown_action")
        if kind is None:
            raise WorkerCommitDeniedError("unknown_resource_kind")
        resource_id = str(config.get("resource_id", job.project_id))
        department = config.get("department")
        return (
            action,
            kind,
            resource_id,
            str(department) if department is not None else None,
            bool(config.get("protected", False)),
        )

    @staticmethod
    def _job_from(index: dict[str, Any], job_id: str) -> Job:
        raw = index["jobs"].get(job_id)
        if raw is None:
            raise JobNotFoundError(f"unknown job: {job_id}")
        return Job.from_dict(raw)

    @staticmethod
    def _require_lease(job: Job, worker_id: str, *, now: datetime) -> None:
        if job.status is JobStatus.CANCELED:
            raise InvalidJobStateError("canceled jobs cannot commit results")
        if job.status is not JobStatus.LEASED:
            raise InvalidJobStateError(f"job is not leased: {job.status.value}")
        if job.worker_id != worker_id:
            raise LeaseOwnershipError("worker does not own the job lease")
        if job.lease_expires_at is None or _parse(job.lease_expires_at) <= _as_utc(now):
            raise LeaseOwnershipError("job lease has expired")

    @staticmethod
    def _retry_or_dead_letter(
        job: Job,
        *,
        failure: JobFailure,
        now: datetime,
        immediate: bool = False,
    ) -> Job:
        attempts = job.attempt_count + 1
        if failure.retryable and attempts < job.max_attempts:
            backoff = 0 if immediate else min(300, 2 ** (attempts - 1))
            return replace(
                job,
                status=JobStatus.RETRY_WAIT if backoff else JobStatus.QUEUED,
                attempt_count=attempts,
                worker_id=None,
                leased_at=None,
                lease_expires_at=None,
                heartbeat_at=None,
                available_at=_stamp(now + timedelta(seconds=backoff)),
                failure=failure,
            )
        return JobService._dead_letter(
            replace(job, attempt_count=attempts),
            failure,
        )

    @staticmethod
    def _dead_letter(job: Job, failure: JobFailure) -> Job:
        return replace(
            job,
            status=JobStatus.DEAD_LETTER,
            worker_id=None,
            leased_at=None,
            lease_expires_at=None,
            heartbeat_at=None,
            failure=failure,
        )

    @staticmethod
    def _trace(
        index: dict[str, Any],
        job: Job,
        event: str,
        *,
        recorded_at: str,
        worker_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        index["trace_events"].append(
            TraceEvent(
                job_id=job.id,
                trace_id=job.trace_id,
                event=event,
                recorded_at=recorded_at,
                worker_id=worker_id,
                detail=detail,
            ).to_dict()
        )

    @staticmethod
    def _validate_enqueue(
        *,
        job_type: str,
        actor_id: str,
        project_id: str,
        idempotency_key: str,
        cost_budget: float,
        timeout_seconds: int,
        max_attempts: int,
        input_fingerprint: str,
        permission_snapshot_id: str,
        trace_id: str,
    ) -> None:
        required = {
            "job_type": job_type,
            "actor_id": actor_id,
            "project_id": project_id,
            "idempotency_key": idempotency_key,
            "input_fingerprint": input_fingerprint,
            "permission_snapshot_id": permission_snapshot_id,
            "trace_id": trace_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"required job fields are empty: {', '.join(sorted(missing))}")
        if cost_budget < 0:
            raise ValueError("cost_budget must be non-negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")

    @staticmethod
    def _cost(value: object, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise ValueError(f"{name} must be numeric")
        try:
            cost = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if cost < 0:
            raise ValueError(f"{name} must be non-negative")
        return cost

    @staticmethod
    def _error_code(error: str | Exception) -> str:
        if isinstance(error, Exception):
            name = type(error).__name__
            return "".join(char.lower() if char.isalnum() else "_" for char in name).strip("_")
        normalized = "".join(
            char.lower() if char.isalnum() else "_" for char in str(error).split(":", 1)[0]
        )
        return normalized.strip("_")[:80] or "job_failed"

    @staticmethod
    def _safe_error_message(error: str | Exception) -> str:
        message = str(error).replace("\n", " ").strip()
        return message[:500] or "job failed without an error message"

    @staticmethod
    def _failure_message(reason: str) -> str:
        return {
            "stale_acl_epoch": "worker authorization used a stale ACL epoch",
            "stale_snapshot": "worker authorization used a stale permission snapshot",
            "stale_input_fingerprint": "job inputs changed before worker commit",
            "cost_budget_exceeded": "actual cost exceeds job budget",
        }.get(reason, f"worker commit denied: {reason}")
