"""Jobs storage stays local, blob-backed, and outside sync-owned tables."""

from __future__ import annotations

from movie_muse.jobs.api import JobStatus


def _table_names(job_stack) -> set[str]:
    rows = job_stack.workspace.store.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return {str(row["name"]) for row in rows}


def test_jobs_add_no_sqlite_tables_and_use_jobs_index_digest(job_stack) -> None:
    before = _table_names(job_stack)
    job_stack.enqueue()
    after = _table_names(job_stack)
    assert after == before
    assert job_stack.workspace.store.get_meta("jobs.index_digest")
    assert "jobs" not in after
    assert "job_outbox" not in after
    assert "job_inbox" not in after


def test_airplane_mode_queue_and_worker_need_no_network(job_stack) -> None:
    job_stack.workspace.set_airplane_mode(True)
    job = job_stack.enqueue()
    leased = job_stack.jobs.lease(
        "offline-worker",
        now=job_stack.clock(),
        lease_seconds=20,
    )
    assert leased is not None
    completed = job_stack.jobs.complete(
        job.id,
        "offline-worker",
        {"local_projection": "ready"},
    )
    assert completed.status is JobStatus.COMPLETED
    assert job_stack.jobs.canonical_result(job.idempotency_key) == {
        "local_projection": "ready"
    }
