"""Status ledger operations: runnable selection, fingerprints, and STALE closure."""

from __future__ import annotations

import subprocess
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from movie_muse.toolchain.fingerprint import compute_item_fingerprint
from movie_muse.toolchain.scopes import (
    ScopeCatalog,
    load_scope_catalog,
    map_files_to_scopes,
    resolve_item_paths,
)
from movie_muse.toolchain.yamlio import dump_round_trip, load_mapping, load_round_trip

PASS_STATUSES = {"PASS"}
CURRENT_PASS = "PASS"
STALE_SOURCE_STATUSES = {"PASS", "STALE"}
EMPTY_OWNED_CHECKED_STATUSES = {"IN_PROGRESS", "PASS", "STALE", "FAIL"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_is_clean(root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def load_manifest_data(root: Path) -> dict[str, Any]:
    return load_mapping(root / "movie_muse_build_status.yaml")


def load_dag_data(root: Path) -> dict[str, Any]:
    return load_mapping(root / "dependency_dag.yaml")


def items_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = manifest.get("items") or []
    return {str(item["id"]): item for item in items}


def reverse_edges(nodes: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        node_id = str(node["id"])
        for dep in node.get("depends_on") or []:
            reverse[str(dep)].append(node_id)
    return {key: sorted(set(value)) for key, value in reverse.items()}


def list_runnable_items(manifest: dict[str, Any]) -> list[str]:
    runnable: list[str] = []
    items = items_by_id(manifest)
    for item_id, item in items.items():
        if item.get("status") == "PASS":
            continue
        dependencies = [str(dep) for dep in (item.get("depends_on") or [])]
        if all(items[dep].get("status") == CURRENT_PASS for dep in dependencies):
            runnable.append(item_id)
    return runnable


def item_dependency_fingerprints(manifest: dict[str, Any], item: dict[str, Any]) -> dict[str, str | None]:
    items = items_by_id(manifest)
    fingerprints: dict[str, str | None] = {}
    for dep in item.get("depends_on") or []:
        record = items[str(dep)].get("pass_record") or {}
        fingerprints[str(dep)] = record.get("input_fingerprint")
    return fingerprints


def fingerprint_item(
    root: Path,
    manifest: dict[str, Any],
    catalog: ScopeCatalog,
    item_id: str,
    *,
    verification_commit: str | None = None,
) -> dict[str, Any]:
    item = items_by_id(manifest)[item_id]
    commit = verification_commit or git_head(root)
    digest, paths = compute_item_fingerprint(
        root=root,
        catalog=catalog,
        item_id=item_id,
        scope_keys=[str(key) for key in item["scope_keys"]],
        verification_commit=commit,
        dependency_fingerprints=item_dependency_fingerprints(manifest, item),
    )
    return {
        "item_id": item_id,
        "verification_commit": commit,
        "input_fingerprint": digest,
        "resolved_paths": paths,
    }


def stale_dependent_closure(manifest: dict[str, Any], roots: Iterable[str]) -> list[str]:
    reverse = reverse_edges(manifest.get("items") or [])
    seen: set[str] = set()
    queue = deque(sorted(set(roots)))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for dependent in reverse.get(current, []):
            if dependent not in seen:
                queue.append(dependent)
    return sorted(seen)


def scopes_for_item_ids(manifest: dict[str, Any], item_ids: Iterable[str]) -> dict[str, list[str]]:
    items = items_by_id(manifest)
    return {item_id: [str(key) for key in items[item_id]["scope_keys"]] for item_id in item_ids}


def invalidate_from_files(
    manifest: dict[str, Any],
    catalog: ScopeCatalog,
    relpaths: Iterable[str],
) -> dict[str, Any]:
    file_map = map_files_to_scopes(catalog, relpaths)
    affected_scopes = sorted({key for keys in file_map.values() for key in keys})
    items = items_by_id(manifest)
    directly_affected = [
        item_id
        for item_id, item in items.items()
        if any(scope in item.get("scope_keys", []) for scope in affected_scopes)
        and item.get("status") in STALE_SOURCE_STATUSES
    ]
    closure = stale_dependent_closure(manifest, directly_affected)
    changed: list[str] = []
    for item_id in closure:
        item = items[item_id]
        if item.get("status") in STALE_SOURCE_STATUSES and item.get("status") != "STALE":
            item["status"] = "STALE"
            changed.append(item_id)
        elif item.get("status") == "PASS":
            item["status"] = "STALE"
            changed.append(item_id)
    if changed:
        manifest["overall_status"] = "STALE"
        manifest["last_updated_utc"] = utc_now()
    return {
        "files": file_map,
        "affected_scopes": affected_scopes,
        "directly_affected": sorted(directly_affected),
        "closure": closure,
        "marked_stale": changed,
    }


def assert_scope_coverage(root: Path, manifest: dict[str, Any], catalog: ScopeCatalog) -> None:
    missing_keys: list[str] = []
    empty_owned: list[str] = []
    for item in manifest.get("items") or []:
        item_id = str(item["id"])
        for key in item.get("scope_keys") or []:
            if key not in catalog.scopes:
                missing_keys.append(f"{item_id}:{key}")
        if item.get("status") in catalog.empty_owned_fail_statuses or item.get("status") in EMPTY_OWNED_CHECKED_STATUSES:
            owned_files = resolve_item_paths(
                root,
                catalog,
                [str(key) for key in item["scope_keys"]],
                for_fingerprint=False,
            )
            if not owned_files:
                empty_owned.append(item_id)
    if missing_keys:
        raise ValueError("manifest scope keys missing from verification-scopes.yaml: " + ", ".join(missing_keys))
    if empty_owned:
        raise ValueError("in-progress/completed items have no resolved scope files: " + ", ".join(empty_owned))


def set_item_status(
    root: Path,
    item_id: str,
    status: str,
    *,
    owner: str | None = None,
    baseline_commit: str | None = None,
) -> dict[str, Any]:
    path = root / "movie_muse_build_status.yaml"
    manifest = load_round_trip(path)
    items = {str(item["id"]): item for item in manifest["items"]}
    if item_id not in items:
        raise KeyError(item_id)
    items[item_id]["status"] = status
    if status == "IN_PROGRESS":
        items[item_id]["blocker"] = None
    if manifest.get("baseline_commit") in (None, "") and baseline_commit:
        manifest["baseline_commit"] = baseline_commit
    if manifest.get("overall_status") in (None, "NOT_STARTED") and status == "IN_PROGRESS":
        manifest["overall_status"] = "IN_PROGRESS"
    manifest["last_updated_utc"] = utc_now()
    dump_round_trip(path, manifest)
    return {
        "item_id": item_id,
        "status": status,
        "owner": owner,
        "updated_utc": manifest["last_updated_utc"],
    }


def record_pass(
    root: Path,
    item_id: str,
    payload: dict[str, Any],
    *,
    confirm_orchestrator: bool,
    catalog: ScopeCatalog | None = None,
) -> dict[str, Any]:
    if not confirm_orchestrator:
        raise PermissionError("record-pass requires --confirm-orchestrator")
    if not git_is_clean(root):
        raise RuntimeError("record-pass requires a clean working tree")
    manifest_data = load_manifest_data(root)
    items = items_by_id(manifest_data)
    item = items[item_id]
    for dep in item.get("depends_on") or []:
        if items[str(dep)].get("status") != "PASS":
            raise RuntimeError(f"{item_id} cannot PASS while {dep} is {items[str(dep)].get('status')}")
    verifier = (payload.get("independent_verifier") or {})
    if verifier.get("result") != "PASS":
        raise RuntimeError("independent verifier result must be PASS")
    required = {
        "verification_commit",
        "input_fingerprint",
        "commands",
        "evidence",
        "completed_at_utc",
        "independent_verifier",
    }
    missing = required - set(payload)
    if missing:
        raise RuntimeError(f"pass payload missing fields: {sorted(missing)}")
    head = git_head(root)
    if payload["verification_commit"] != head:
        raise RuntimeError(
            f"verification_commit {payload['verification_commit']} does not match HEAD {head}"
        )
    catalog = catalog or load_scope_catalog(root)
    computed = fingerprint_item(
        root,
        manifest_data,
        catalog,
        item_id,
        verification_commit=head,
    )
    if payload["input_fingerprint"] != computed["input_fingerprint"]:
        raise RuntimeError("input_fingerprint does not match recomputed fingerprint")
    path = root / "movie_muse_build_status.yaml"
    manifest = load_round_trip(path)
    live_items = {str(entry["id"]): entry for entry in manifest["items"]}
    live_items[item_id]["status"] = "PASS"
    live_items[item_id]["pass_record"] = payload
    live_items[item_id]["blocker"] = None
    if all(entry.get("status") == "PASS" for entry in manifest["items"]):
        manifest["overall_status"] = "PASS"
    else:
        manifest["overall_status"] = "IN_PROGRESS"
    manifest["last_updated_utc"] = utc_now()
    dump_round_trip(path, manifest)
    return {"item_id": item_id, "status": "PASS", "input_fingerprint": payload["input_fingerprint"]}


def load_workspace(root: Path) -> tuple[dict[str, Any], dict[str, Any], ScopeCatalog]:
    return load_manifest_data(root), load_dag_data(root), load_scope_catalog(root)
