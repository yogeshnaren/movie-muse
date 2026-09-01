"""Durable queue, retry, cancellation, quota, and once-only behavior."""

from __future__ import annotations

import pytest

from movie_muse.audit.api import PolicyDecision
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.jobs.api import (
    InvalidJobStateError,
    JobStatus,
    OutboxStatus,
    WorkerCommitDeniedError,
)


def test_enqueue_lease_heartbeat_complete_happy_path(job_stack) -> None:
    job = job_stack.enqueue(trace_id="trace-happy")
    leased = job_stack.jobs.lease("worker-a", now=job_stack.clock(), lease_seconds=20)
    assert leased is not None
    assert leased.id == job.id
    assert leased.status is JobStatus.LEASED

    job_stack.clock.advance(5)
    heartbeat = job_stack.jobs.heartbeat(job.id, "worker-a", progress=0.4)
    assert heartbeat.progress == 0.4
    completed = job_stack.jobs.complete(job.id, "worker-a", {"projection_id": "projection-1"})

    assert completed.status is JobStatus.COMPLETED
    assert completed.progress == 1.0
    assert job_stack.jobs.result(job.id) == {"projection_id": "projection-1"}
    assert job_stack.jobs.canonical_result(job.idempotency_key) == {
        "projection_id": "projection-1"
    }
    assert job_stack.jobs.applied_mutation_count(job.idempotency_key) == 1
    assert job_stack.jobs.list_outbox()[0].status is OutboxStatus.DELIVERED
    events = job_stack.jobs.trace_events(job.id)
    assert [event.event for event in events] == [
        "enqueued",
        "leased",
        "heartbeat",
        "completed",
    ]
    assert all(event.trace_id == "trace-happy" for event in events)
    assert "durable worker wakes" not in repr(events).lower()


def test_duplicate_idempotency_key_returns_existing_job(job_stack) -> None:
    first = job_stack.enqueue(idempotency_key="same-request")
    duplicate = job_stack.enqueue(
        idempotency_key="same-request",
        payload={"authorization": {"action": "propose"}, "different": True},
    )
    assert duplicate == first

    leased = job_stack.jobs.lease("worker-a", now=job_stack.clock(), lease_seconds=20)
    assert leased is not None
    job_stack.jobs.complete(first.id, "worker-a", {"result": "once"})

    assert job_stack.jobs.applied_mutation_count("same-request") == 1
    assert len(job_stack.jobs.list_outbox()) == 1
    assert job_stack.jobs.lease(
        "worker-b", now=job_stack.clock(), lease_seconds=20
    ) is None


def test_higher_priority_then_fifo(job_stack) -> None:
    low = job_stack.enqueue(priority=1)
    first_high = job_stack.enqueue(priority=99)
    second_high = job_stack.enqueue(priority=99)
    leased_one = job_stack.jobs.lease("worker-a", now=job_stack.clock(), lease_seconds=20)
    assert leased_one is not None
    assert leased_one.id == first_high.id
    job_stack.jobs.cancel(first_high.id, job_stack.owner.id)
    leased_two = job_stack.jobs.lease("worker-b", now=job_stack.clock(), lease_seconds=20)
    assert leased_two is not None
    assert leased_two.id == second_high.id
    job_stack.jobs.cancel(second_high.id, job_stack.owner.id)
    leased_three = job_stack.jobs.lease("worker-c", now=job_stack.clock(), lease_seconds=20)
    assert leased_three is not None
    assert leased_three.id == low.id


def test_retry_backoff_then_dead_letter_is_explainable(job_stack) -> None:
    job = job_stack.enqueue(max_attempts=2)
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    retrying = job_stack.jobs.fail(
        job.id,
        "worker-a",
        "provider_unavailable: temporary outage",
        retryable=True,
    )
    assert retrying.status is JobStatus.RETRY_WAIT
    assert retrying.attempt_count == 1
    assert retrying.failure is not None
    assert retrying.failure.code == "provider_unavailable"
    assert job_stack.jobs.lease(
        "worker-b", now=job_stack.clock(), lease_seconds=20
    ) is None

    job_stack.clock.advance(1)
    assert job_stack.jobs.lease(
        "worker-b", now=job_stack.clock(), lease_seconds=20
    ) is not None
    dead = job_stack.jobs.fail(
        job.id,
        "worker-b",
        "provider_unavailable: still unavailable",
        retryable=True,
    )
    assert dead.status is JobStatus.DEAD_LETTER
    assert dead.attempt_count == 2
    assert dead.failure is not None
    assert dead.failure.retryable is True
    assert "still unavailable" in dead.failure.message


def test_cancel_prevents_leased_job_commit(job_stack) -> None:
    job = job_stack.enqueue()
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    canceled = job_stack.jobs.cancel(job.id, job_stack.owner.id)
    assert canceled.status is JobStatus.CANCELED
    with pytest.raises(InvalidJobStateError, match="canceled"):
        job_stack.jobs.complete(job.id, "worker-a", {"should_not": "apply"})
    assert job_stack.jobs.canonical_result(job.idempotency_key) is None


def test_estimated_and_actual_cost_budgets_fail_closed(job_stack) -> None:
    estimated = job_stack.enqueue(
        payload={"authorization": {"action": "propose"}, "estimated_cost": 6.0},
        cost_budget=5.0,
    )
    assert estimated.status is JobStatus.DEAD_LETTER
    assert estimated.failure is not None
    assert estimated.failure.code == "cost_budget_exceeded"

    actual = job_stack.enqueue(cost_budget=2.0)
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    with pytest.raises(WorkerCommitDeniedError, match="cost_budget_exceeded"):
        job_stack.jobs.complete(actual.id, "worker-a", {"actual_cost": 2.01})
    rejected = job_stack.jobs.get(actual.id)
    assert rejected.status is JobStatus.DEAD_LETTER
    assert rejected.failure is not None
    assert rejected.failure.code == "cost_budget_exceeded"
    assert job_stack.jobs.canonical_result(actual.idempotency_key) is None


def test_duplicate_outbox_replay_applies_once(job_stack) -> None:
    job = job_stack.enqueue(idempotency_key="outbox-once")
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    job_stack.jobs.complete(job.id, "worker-a", {"canonical": "result"})
    intent = job_stack.jobs.list_outbox()[0]

    assert job_stack.jobs.replay_outbox(intent.id) is False
    assert job_stack.jobs.replay_pending_outbox() == 0
    assert job_stack.jobs.applied_mutation_count("outbox-once") == 1
    assert job_stack.jobs.list_outbox()[0].delivery_count == 1


def test_worker_stale_acl_and_snapshot_deny_commit(job_stack) -> None:

    writer = make_human_actor(
        organization_id=job_stack.project.organization_id, display_name="Writer"
    )
    job_stack.identity.register_actor(writer)
    invitation = job_stack.identity.invite(
        inviter_actor_id=job_stack.owner.id,
        invitee_actor_id=writer.id,
        project_id=job_stack.project.id,
        role=Role.WRITER,
    )
    job_stack.identity.accept_invitation(invitation.id, actor_id=writer.id)
    membership = next(
        item
        for item in job_stack.identity.list_memberships()
        if item.actor_id == writer.id and item.project_id == job_stack.project.id
    )
    job = job_stack.enqueue(actor_id=writer.id)
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    job_stack.identity.revoke_membership(membership.id, actor_id=job_stack.owner.id)
    with pytest.raises(WorkerCommitDeniedError, match="stale_acl_epoch"):
        job_stack.jobs.complete(job.id, "worker-a", {"should_not": "apply"})
    denied = job_stack.jobs.get(job.id)
    assert denied.status is JobStatus.DEAD_LETTER
    assert job_stack.jobs.canonical_result(job.idempotency_key) is None
    assert any(
        record.operation == "worker_commit" and record.policy_decision is PolicyDecision.DENY
        for record in job_stack.audit.list_records()
    )


def test_worker_stale_input_fingerprint_denies_commit(job_stack) -> None:
    job = job_stack.enqueue()
    assert job_stack.jobs.lease(
        "worker-a", now=job_stack.clock(), lease_seconds=20
    ) is not None
    job_stack.fingerprints[job_stack.project.id] = "input-v2"
    with pytest.raises(WorkerCommitDeniedError, match="stale_input_fingerprint"):
        job_stack.jobs.complete(job.id, "worker-a", {"stale": True})
    rejected = job_stack.jobs.get(job.id)
    assert rejected.status is JobStatus.RETRY_WAIT
    assert rejected.failure is not None
    assert rejected.failure.code == "stale_input_fingerprint"
    assert job_stack.jobs.canonical_result(job.idempotency_key) is None
