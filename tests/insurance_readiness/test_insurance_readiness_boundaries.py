"""Hosts import movie_muse.insurance_readiness.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_insurance_readiness_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "insurance_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.insurance_readiness.api import InsuranceReadinessService\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_insurance_readiness_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "insurance_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.insurance_readiness.service import InsuranceReadinessService\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_insurance_readiness_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "insurance_readiness"
    siblings = (
        "artifacts",
        "audit",
        "authorization",
        "breakdown",
        "budget",
        "dependencies",
        "identity",
        "persistence",
        "scheduling",
        "schemas",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from movie_muse.model_router" not in text
        assert "from tests." not in text


def test_ext_insurance_partner_gate_stays_not_run() -> None:
    """Contract tests are not live handoff. Ledger stays NOT_RUN until genuine PASS."""

    manifest = yaml.safe_load(
        (repo_root() / "movie_muse_build_status.yaml").read_text(encoding="utf-8")
    )
    gates = {item["id"]: item for item in manifest["external_gates"]}
    gate = gates["EXT-INSURANCE-PARTNER"]
    assert gate["owner_item"] == "MM-039"
    status = str(gate["status"])
    assert status in {"NOT_RUN", "PASS"}
    evidence = list(gate.get("evidence") or [])
    if status == "NOT_RUN":
        assert evidence == []
    else:
        assert evidence
