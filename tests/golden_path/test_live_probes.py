"""Required live/sandbox probes fail closed when providers are unset."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from movie_muse.toolchain.paths import repo_root


def _load_probes():
    path = repo_root() / "scripts" / "gates" / "_live_probes.py"
    spec = importlib.util.spec_from_file_location("mm047_live_probes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.architecture
def test_live_probes_fail_closed_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    probes = _load_probes()
    for name in probes.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    missing = probes.probe_all()
    assert tuple(missing) == probes.REQUIRED_LIVE_GATES
    assert probes.main() == 1


@pytest.mark.architecture
def test_external_live_providers_gate_runs_probes() -> None:
    text = (repo_root() / "scripts" / "gates" / "external_live_providers.sh").read_text(
        encoding="utf-8"
    )
    assert "_live_probes.py" in text
    assert "_run_pytest_isolated_live.sh" in text
    assert (repo_root() / "scripts" / "gates" / "_live_probes.py").is_file()
    golden = (repo_root() / "scripts" / "gates" / "golden_path_41_steps.sh").read_text(
        encoding="utf-8"
    )
    assert "_run_pytest_isolated_live.sh" not in golden


def _run_gate_pytest(script_name: str, *pytest_args: str) -> subprocess.CompletedProcess[str]:
    root = repo_root()
    script = root / "scripts" / "gates" / script_name
    assert script.is_file()
    return subprocess.run(
        [str(script), *pytest_args],
        cwd=root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.architecture
def test_isolated_contract_pytest_preserves_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    zoom_env = "MOVIE_MUSE_ZOOM_SANDBOX_BASE_URL"
    fdx_env = "MOVIE_MUSE_FINAL_DRAFT_BIN"
    monkeypatch.setenv(zoom_env, "https://zoom.example.invalid/sandbox")
    monkeypatch.setenv(fdx_env, sys.executable)
    leaked = _run_gate_pytest(
        "_run_pytest.sh",
        "tests/fdx/test_final_draft_unavailable.py::test_ext_gate_env_name_is_stable",
    )
    assert leaked.returncode != 0
    isolated_fdx = _run_gate_pytest(
        "_run_pytest_isolated_live.sh",
        "tests/fdx/test_final_draft_unavailable.py::test_ext_gate_env_name_is_stable",
    )
    assert isolated_fdx.returncode == 0, isolated_fdx.stdout + isolated_fdx.stderr
    isolated_zoom = _run_gate_pytest(
        "_run_pytest_isolated_live.sh",
        "tests/adapters/zoom/test_zoom_contracts.py::test_live_sandbox_unset_fails_closed",
    )
    assert isolated_zoom.returncode == 0, isolated_zoom.stdout + isolated_zoom.stderr
    assert os.environ.get(zoom_env) == "https://zoom.example.invalid/sandbox"
    assert os.environ.get(fdx_env) == sys.executable


@pytest.mark.architecture
def test_owner_ext_ledger_tests_allow_recorded_pass() -> None:
    """Contract pytest must not hard-fail after genuine YAML EXT PASS."""

    root = repo_root()
    paths = (
        root / "tests" / "adapters" / "zoom" / "test_zoom_boundaries.py",
        root / "tests" / "adapters" / "google_meet" / "test_google_meet_boundaries.py",
        root / "tests" / "storyboard" / "test_storyboard_boundaries.py",
        root / "tests" / "video_previs" / "test_video_previs_boundaries.py",
        root / "tests" / "insurance_readiness" / "test_insurance_readiness_boundaries.py",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert 'in {"NOT_RUN", "PASS"}' in text, path
        assert 'assert gate["status"] == "NOT_RUN"' not in text, path
