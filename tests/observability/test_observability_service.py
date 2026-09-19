"""Redacted traces, metrics, and SLOs."""

from __future__ import annotations

import pytest

from movie_muse.observability.api import REDACTION_MARK, ContentLeakageError, SloBreachError
from movie_muse.security.api import ControlPlane
from movie_muse.toolchain.paths import repo_root


def test_prompt_attributes_are_redacted(plane: ControlPlane) -> None:
    trace = plane.observability.emit_trace(
        "read_revision",
        principal=plane.principal,
        acl_epoch=plane.epoch,
        attributes={"prompt": "INT. KITCHEN - DAY", "route": "local"},
    )
    assert trace.id.startswith("trc_")
    assert trace.attributes["prompt"] == REDACTION_MARK
    assert trace.attributes["route"] == "local"
    stored = plane.observability.list_traces()
    assert stored[0].attributes["prompt"] == REDACTION_MARK


def test_unredacted_screenplay_content_fails_closed(plane: ControlPlane) -> None:
    with pytest.raises(ContentLeakageError):
        plane.observability.emit_trace(
            "read_revision",
            principal=plane.principal,
            acl_epoch=plane.epoch,
            attributes={"note": "INT. KITCHEN - DAY"},
        )


def test_metric_and_availability_slo(plane: ControlPlane) -> None:
    sample = plane.observability.emit_metric(
        "jobs_completed",
        1.0,
        principal=plane.principal,
        acl_epoch=plane.epoch,
        labels={"queue": "previs"},
    )
    assert sample.name == "jobs_completed"
    with pytest.raises(SloBreachError):
        plane.observability.assert_slo("availability")
    for _ in range(20):
        plane.observability.record_slo_sample(
            "availability",
            success=True,
            latency_ms=12.0,
            principal=plane.principal,
            acl_epoch=plane.epoch,
        )
    plane.observability.assert_slo("availability")
    plane.observability.record_slo_sample(
        "latency_ms_p99",
        success=True,
        latency_ms=40.0,
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    plane.observability.assert_slo("latency_ms_p99")


@pytest.mark.architecture
def test_observability_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "observability"
    siblings = ("audit", "authorization", "identity", "jobs", "persistence", "schemas", "security")
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from tests." not in text
