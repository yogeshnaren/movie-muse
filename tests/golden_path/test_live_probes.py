"""Required live/sandbox probes fail closed when providers are unset."""

from __future__ import annotations

import importlib.util

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
    assert (repo_root() / "scripts" / "gates" / "_live_probes.py").is_file()
