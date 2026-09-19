"""Crash recovery and duplicate provider/outbox delivery behavior."""

from __future__ import annotations

from movie_muse.jobs.api import JobStatus


def test_kill_restart_releases_stale_lease_and_applies_result_once(worker_stack) -> None:
    job = worker_stack.enqueue(idempotency_key="crash-recovery", max_attempts=3)
    first_worker = worker_stack.worker("worker-before-crash", lease_seconds=10)
    leased = first_worker.lease(now=worker_stack.clock())
    assert leased is not None
    first_worker.record_provider_response(
        job.id,
        delivery_id="provider-delivery-1",
        response={"projection": "durable"},
        actual_cost=1.25,
    )

    worker_stack.restart()
    worker_stack.clock.advance(11)
    replacement = worker_stack.worker("worker-after-restart", lease_seconds=10)
    recovered = replacement.lease(now=worker_stack.clock())
    assert recovered is not None
    assert recovered.id == job.id
    assert recovered.attempt_count == 1
    completed = replacement.persist_provider_result(
        job.id,
        delivery_id="provider-delivery-1",
    )

    assert completed.status is JobStatus.COMPLETED
    assert completed.actual_cost == 1.25
    assert worker_stack.jobs.canonical_result("crash-recovery") == {
        "projection": "durable"
    }
    assert worker_stack.jobs.applied_mutation_count("crash-recovery") == 1
    assert replacement.recover_pending_outbox() == 0


def test_duplicate_provider_delivery_and_outbox_replay_apply_once(worker_stack) -> None:
    job = worker_stack.enqueue(idempotency_key="provider-once")
    worker = worker_stack.worker("provider-worker")
    assert worker.lease(now=worker_stack.clock()) is not None
    first = worker.record_provider_response(
        job.id,
        delivery_id="same-delivery",
        response={"provider_result": "candidate"},
        actual_cost=0.75,
    )
    duplicate = worker.record_provider_response(
        job.id,
        delivery_id="same-delivery",
        response={"provider_result": "candidate"},
        actual_cost=0.75,
    )
    assert duplicate == first

    worker.persist_provider_result(job.id, delivery_id="same-delivery")
    intent = worker_stack.jobs.list_outbox()[0]
    assert worker_stack.jobs.replay_outbox(intent.id) is False
    assert worker_stack.jobs.applied_mutation_count("provider-once") == 1
    assert worker_stack.jobs.canonical_result("provider-once") == {
        "provider_result": "candidate"
    }
