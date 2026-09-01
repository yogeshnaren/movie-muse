from __future__ import annotations

import subprocess

import pytest

from movie_muse.toolchain.paths import repo_root


@pytest.mark.toolchain
def test_verify_all_stays_fail_closed_until_all_gates_exist() -> None:
    root = repo_root()
    result = subprocess.run(
        [str(root / "scripts" / "verify_all.sh")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS" not in result.stdout.splitlines()
    assert "NOT_READY" in output
    assert "migrations_backup_and_recovery" in output
