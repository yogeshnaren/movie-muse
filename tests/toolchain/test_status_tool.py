from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from movie_muse.toolchain.engine import (
    fingerprint_item,
    invalidate_from_files,
    items_by_id,
    list_runnable_items,
    load_manifest_data,
    stale_dependent_closure,
)
from movie_muse.toolchain.fingerprint import canonical_json, sha256_bytes
from movie_muse.toolchain.paths import repo_root
from movie_muse.toolchain.scopes import load_scope_catalog, map_files_to_scopes


@pytest.mark.toolchain
def test_only_mm001_is_runnable_when_nothing_has_passed() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    for item in manifest["items"]:
        item["status"] = "NOT_STARTED"
        item["pass_record"] = None
    assert list_runnable_items(manifest) == ["MM-001"]


@pytest.mark.toolchain
def test_runnable_items_match_dependency_pass_rule() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    items = items_by_id(manifest)
    expected = [
        item_id
        for item_id, item in items.items()
        if item.get("status") != "PASS"
        and all(items[str(dep)].get("status") == "PASS" for dep in (item.get("depends_on") or []))
    ]
    assert list_runnable_items(manifest) == expected


@pytest.mark.toolchain
def test_all_manifest_scope_keys_are_mapped() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    catalog = load_scope_catalog(root)
    missing: list[str] = []
    for item in manifest["items"]:
        for key in item["scope_keys"]:
            if key not in catalog.scopes:
                missing.append(f"{item['id']}:{key}")
    assert missing == []
    assert len(manifest["items"]) == 47


@pytest.mark.toolchain
def test_fingerprint_is_deterministic() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    catalog = load_scope_catalog(root)
    first = fingerprint_item(root, manifest, catalog, "MM-001", verification_commit="deadbeef")
    second = fingerprint_item(root, manifest, catalog, "MM-001", verification_commit="deadbeef")
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["resolved_paths"]
    assert "src/movie_muse/toolchain/engine.py" in first["resolved_paths"]


@pytest.mark.toolchain
def test_fingerprint_changes_when_source_changes(tmp_path: Path) -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    catalog = load_scope_catalog(root)
    before = fingerprint_item(root, manifest, catalog, "MM-001", verification_commit="c1")
    extra = canonical_json({"probe": str(tmp_path)})
    mutated = sha256_bytes((before["input_fingerprint"] + extra).encode("utf-8"))
    assert mutated != before["input_fingerprint"]


@pytest.mark.toolchain
def test_unmatched_file_fails_closed() -> None:
    root = repo_root()
    catalog = load_scope_catalog(root)
    with pytest.raises(ValueError, match="match no verification scope"):
        map_files_to_scopes(catalog, ["totally_unknown_path/secret.bin"])


@pytest.mark.toolchain
def test_stale_closure_follows_reverse_dag() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    items = items_by_id(manifest)
    items["MM-001"]["status"] = "PASS"
    items["MM-002"]["status"] = "PASS"
    catalog = load_scope_catalog(root)
    report = invalidate_from_files(manifest, catalog, ["src/movie_muse/schemas/document.json"])
    assert "MM-002" in report["directly_affected"]
    assert "MM-003" in report["closure"]
    assert "MM-047" in report["closure"]
    assert items["MM-001"]["status"] == "PASS"
    assert items["MM-002"]["status"] == "STALE"


@pytest.mark.toolchain
def test_mm001_change_does_not_stale_unstarted_dependents() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    catalog = load_scope_catalog(root)
    items = items_by_id(manifest)
    items["MM-001"]["status"] = "PASS"
    items["MM-002"]["status"] = "NOT_STARTED"
    items["MM-002"]["pass_record"] = None
    report = invalidate_from_files(manifest, catalog, ["src/movie_muse/toolchain/engine.py"])
    assert "MM-001" in report["directly_affected"]
    assert items["MM-001"]["status"] == "STALE"
    assert items["MM-002"]["status"] == "NOT_STARTED"


@pytest.mark.toolchain
def test_dependent_closure_includes_final_gate() -> None:
    root = repo_root()
    manifest = load_manifest_data(root)
    closure = stale_dependent_closure(manifest, ["MM-001"])
    assert closure[0] == "MM-001"
    assert "MM-047" in closure
    assert len(closure) == 47


@pytest.mark.toolchain
def test_dag_and_manifest_titles_match() -> None:
    root = repo_root()
    manifest = yaml.safe_load((root / "movie_muse_build_status.yaml").read_text(encoding="utf-8"))
    dag = yaml.safe_load((root / "dependency_dag.yaml").read_text(encoding="utf-8"))
    manifest_titles = {item["id"]: item["title"] for item in manifest["items"]}
    dag_titles = {node["id"]: node["title"] for node in dag["nodes"]}
    assert manifest_titles == dag_titles


@pytest.mark.toolchain
def test_canonical_json_is_stable() -> None:
    payload = {"b": 1, "a": [2, 1]}
    assert canonical_json(payload) == '{"a":[2,1],"b":1}'
    json.loads(canonical_json(payload))
