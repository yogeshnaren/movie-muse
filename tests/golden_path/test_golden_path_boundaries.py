"""Golden-path tests import public APIs only and never other test packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root

REQUIRED_GATES = (
    "manifest_and_staleness",
    "static_quality_and_boundaries",
    "migrations_backup_and_recovery",
    "unit_and_property",
    "integration_sync_concurrency_and_crash",
    "layout_render_and_fdx",
    "ai_contract_and_evaluation",
    "security_privacy_and_rights",
    "api_mcp_webhooks",
    "web_desktop_and_mobile",
    "external_live_providers",
    "competitive_regressions",
    "golden_path_41_steps",
)


@pytest.mark.architecture
def test_host_importing_public_apis_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "golden_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.platforms.api import open_platform\n"
        "from movie_muse.security.api import ControlPlane\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_golden_path_tests_do_not_import_other_test_packages() -> None:
    package = repo_root() / "tests" / "golden_path"
    for path in package.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from tests.")
            assert not stripped.startswith("import tests.")


@pytest.mark.architecture
def test_all_named_verify_all_gates_exist_and_are_executable() -> None:
    root = repo_root()
    gates = root / "scripts" / "gates"
    for name in REQUIRED_GATES:
        script = gates / f"{name}.sh"
        assert script.is_file(), f"missing gate script {name}"
        assert script.stat().st_mode & 0o111, f"gate {name} is not executable"
    verify_all = (root / "scripts" / "verify_all.sh").read_text(encoding="utf-8")
    for name in REQUIRED_GATES:
        assert name in verify_all
    helper = gates / "_run_pytest.sh"
    assert helper.is_file()
    assert helper.stat().st_mode & 0o111


@pytest.mark.architecture
def test_golden_path_allows_all_required_ext_gates_to_pass() -> None:
    text = (repo_root() / "tests" / "golden_path" / "test_golden_path_journey.py").read_text(
        encoding="utf-8"
    )
    assert "must remain visible when not PASS" not in text
    assert "_configured_or_fail_closed" in text
