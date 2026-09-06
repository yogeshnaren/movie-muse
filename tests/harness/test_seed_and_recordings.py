"""Golden-path seed and provider-recording doubles. Offline only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.model_router.api import AdapterResult
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.testkit.api import (
    list_recordings,
    load_adapter_result,
    load_golden_path_project,
    load_recording,
)


def test_golden_path_seed_loads_offline(tmp_path: Path) -> None:
    workspace = LocalWorkspace(tmp_path / "golden")
    seed = load_golden_path_project(workspace)
    status = workspace.status()
    assert status.connectivity_offline is True
    assert seed.revision_head_id
    assert seed.revisions.canon_head_id() == seed.revision_head_id
    reopened = workspace.reopen(seed.document.id)
    assert reopened.id == seed.document.id
    assert seed.licensed_source.classification.value == "licensed"
    assert seed.unlicensed_source.classification.value == "unlicensed"
    assert seed.derived_node.record.input_ids
    assert seed.source_node.id in seed.derived_node.record.input_ids
    assert seed.rights_node.id in seed.derived_node.record.input_ids
    workspace.close()


def test_recordings_are_double_compatible_and_not_live() -> None:
    names = list_recordings()
    assert "extract_structure" in names
    assert "generate_text" in names
    assert "retrieve" in names
    for name in names:
        payload = load_recording(name)
        assert payload["live"] is False
        assert payload["network"] is False
        result = load_adapter_result(name)
        assert isinstance(result, AdapterResult)
        assert result.actual_cost == 0.0
        assert result.method == "deterministic_fixture"
        assert "no_network" in result.assumptions
        assert "not_a_human_sample" in result.assumptions
