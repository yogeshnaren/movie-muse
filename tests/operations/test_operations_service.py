"""SBOM, cost caps, backup/restore, and independent incident drills."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.operations.api import RUNBOOK_STEPS, CostCapError, IncidentError
from movie_muse.security.api import ControlPlane
from movie_muse.toolchain.paths import repo_root


def test_sbom_includes_declared_pins(plane: ControlPlane) -> None:
    sbom = plane.operations.generate_sbom(principal=plane.principal, acl_epoch=plane.epoch)
    assert sbom.id.startswith("sbm_")
    names = {item.name: item.version for item in sbom.packages}
    assert names["ruff"] == "0.12.12"
    assert names["mypy"] == "1.17.1"
    assert names["pytest"] == "8.4.1"
    assert plane.operations.latest_sbom().id == sbom.id


def test_cost_cap_fails_closed(plane: ControlPlane) -> None:
    plane.operations.set_cost_cap(1.0, principal=plane.principal, acl_epoch=plane.epoch)
    plane.operations.record_spend(0.5, principal=plane.principal, acl_epoch=plane.epoch)
    with pytest.raises(CostCapError):
        plane.operations.record_spend(0.6, principal=plane.principal, acl_epoch=plane.epoch)
    plane.operations.assert_within_cap()


def test_incident_requires_independent_reproduction(plane: ControlPlane, tmp_path: Path) -> None:
    incident = plane.operations.open_incident(
        "restore drill",
        severity="high",
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    assert incident.id.startswith("inc_")
    with pytest.raises(IncidentError):
        plane.operations.close_incident(incident.id, principal=plane.principal, acl_epoch=plane.epoch)
    executed = plane.operations.execute_runbook(
        incident.id,
        tmp_path / "backup",
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    assert executed.backup_path is not None
    reproduced = plane.operations.reproduce_independently(
        incident.id,
        tmp_path / "restored",
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    assert reproduced.independently_reproduced is True
    closed = plane.operations.close_incident(
        incident.id, principal=plane.principal, acl_epoch=plane.epoch
    )
    assert closed.status == "closed"
    assert "snapshot_workspace" in RUNBOOK_STEPS
    assert (tmp_path / "restored" / "movie_muse.sqlite").is_file()


@pytest.mark.architecture
def test_operations_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "operations"
    siblings = ("audit", "authorization", "identity", "persistence", "schemas", "toolchain")
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            toolchain_root = "from movie_muse.toolchain.paths import"
            remainder = text.replace(public_import, "").replace(toolchain_root, "")
            assert private_prefix not in remainder
        assert "from tests." not in text
