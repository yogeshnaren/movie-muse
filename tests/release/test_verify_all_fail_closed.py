from __future__ import annotations

import subprocess

import pytest

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


@pytest.mark.toolchain
def test_verify_all_never_prints_a_false_pass() -> None:
    """Fail-closed until every named gate exists; never print PASS except as the final line."""

    root = repo_root()
    missing = [
        name
        for name in REQUIRED_GATES
        if not (root / "scripts" / "gates" / f"{name}.sh").is_file()
    ]
    result = subprocess.run(
        [str(root / "scripts" / "verify_all.sh")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if missing:
        assert result.returncode != 0
        assert "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS" not in result.stdout.splitlines()
        assert "NOT_READY" in output
        assert missing[0] in output
        return
    if result.returncode == 0:
        assert lines[-1] == "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS"
        return
    assert "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS" not in result.stdout.splitlines()
