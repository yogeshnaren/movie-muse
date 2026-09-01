"""Unlicensed rights fixtures fail closed through RightsService."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.persistence.api import LocalWorkspace
from movie_muse.rights.api import PermittedUse, UnlicensedSourceError
from movie_muse.testkit.api import load_golden_path_project, load_rights_fixture


def test_unlicensed_rights_fixture_is_blocked(tmp_path: Path) -> None:
    workspace = LocalWorkspace(tmp_path / "ws")
    seed = load_golden_path_project(workspace)
    unlicensed = load_rights_fixture("unlicensed")
    assert seed.unlicensed_source.classification.value == unlicensed["classification"]
    with pytest.raises(UnlicensedSourceError):
        seed.rights.require_permitted_use(
            seed.unlicensed_source.source_id, PermittedUse.CITATION
        )
    with pytest.raises(UnlicensedSourceError):
        seed.rights.require_permitted_use(
            seed.unlicensed_source.source_id, PermittedUse.RETRIEVAL
        )
    decision = seed.rights.require_permitted_use(
        seed.licensed_source.source_id, PermittedUse.CITATION
    )
    assert decision.allowed is True
    workspace.close()
