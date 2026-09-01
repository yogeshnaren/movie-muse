"""Command-line interface for the Movie Muse status and quality toolchain."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from movie_muse.toolchain.boundaries import scan_boundaries
from movie_muse.toolchain.engine import (
    assert_scope_coverage,
    fingerprint_item,
    git_head,
    invalidate_from_files,
    list_runnable_items,
    load_manifest_data,
    load_workspace,
    record_pass,
    set_item_status,
)
from movie_muse.toolchain.paths import repo_root
from movie_muse.toolchain.scopes import map_files_to_scopes
from movie_muse.toolchain.secrets import scan_secrets
from movie_muse.toolchain.yamlio import load_mapping


def _print(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def cmd_validate(root: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "validate_handoff.py")],
        cwd=root,
    )
    if result.returncode != 0:
        return result.returncode
    manifest, _dag, catalog = load_workspace(root)
    assert_scope_coverage(root, manifest, catalog)
    print("STATUS_VALIDATE=PASS")
    return 0


def cmd_runnable(root: Path) -> int:
    manifest = load_manifest_data(root)
    runnable = list_runnable_items(manifest)
    _print({"runnable": runnable, "count": len(runnable)})
    return 0


def cmd_fingerprint(root: Path, item_id: str) -> int:
    manifest, _dag, catalog = load_workspace(root)
    _print(fingerprint_item(root, manifest, catalog, item_id))
    return 0


def cmd_map_files(root: Path, files: Sequence[str]) -> int:
    _manifest, _dag, catalog = load_workspace(root)
    _print(map_files_to_scopes(catalog, files))
    return 0


def cmd_invalidate(root: Path, files: Sequence[str], apply: bool) -> int:
    manifest, _dag, catalog = load_workspace(root)
    report = invalidate_from_files(manifest, catalog, files)
    if apply:
        from movie_muse.toolchain.yamlio import dump_round_trip, load_round_trip

        path = root / "movie_muse_build_status.yaml"
        live = load_round_trip(path)
        live_report = invalidate_from_files(live, catalog, files)
        dump_round_trip(path, live)
        report = live_report
        report["applied"] = True
    else:
        report["applied"] = False
    _print(report)
    return 0


def cmd_start(root: Path, item_id: str, owner: str) -> int:
    manifest = load_manifest_data(root)
    items = {item["id"]: item for item in manifest["items"]}
    if item_id not in items:
        raise SystemExit(f"unknown item {item_id}")
    if items[item_id]["status"] != "IN_PROGRESS":
        runnable = list_runnable_items(manifest)
        if item_id not in runnable:
            raise SystemExit(f"{item_id} is not DAG-runnable")
    baseline = manifest.get("baseline_commit") or git_head(root)
    result = set_item_status(
        root,
        item_id,
        "IN_PROGRESS",
        owner=owner,
        baseline_commit=baseline,
    )
    _print(result)
    return 0


def cmd_record_pass(root: Path, item_id: str, payload_path: Path, confirm: bool) -> int:
    payload = load_mapping(payload_path)
    result = record_pass(root, item_id, payload, confirm_orchestrator=confirm)
    _print(result)
    return 0


def cmd_boundaries(root: Path) -> int:
    violations = scan_boundaries(root)
    _print({"violations": [item.__dict__ for item in violations], "count": len(violations)})
    return 0 if not violations else 1


def cmd_secrets(root: Path) -> int:
    hits = scan_secrets(root)
    report = root / "evidence" / "secret-scan.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{hit.path}:{hit.line}:{hit.kind}" for hit in hits]
    report.write_text("\n".join(lines) + ("\n" if lines else "CLEAN\n"), encoding="utf-8")
    _print({"hits": [hit.__dict__ for hit in hits], "count": len(hits), "report": str(report)})
    return 0 if not hits else 1


def cmd_check_scopes(root: Path) -> int:
    manifest, _dag, catalog = load_workspace(root)
    assert_scope_coverage(root, manifest, catalog)
    print("SCOPE_COVERAGE=PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mm_status", description="Movie Muse status toolchain")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("runnable")
    sub.add_parser("check-scopes")
    sub.add_parser("boundaries")
    sub.add_parser("secrets")
    fp = sub.add_parser("fingerprint")
    fp.add_argument("item_id")
    mapped = sub.add_parser("map-files")
    mapped.add_argument("files", nargs="+")
    inv = sub.add_parser("invalidate")
    inv.add_argument("files", nargs="+")
    inv.add_argument("--apply", action="store_true")
    start = sub.add_parser("start")
    start.add_argument("item_id")
    start.add_argument("--owner", default="orchestrator")
    rec = sub.add_parser("record-pass")
    rec.add_argument("item_id")
    rec.add_argument("--payload", required=True)
    rec.add_argument("--confirm-orchestrator", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = repo_root()
    try:
        if args.command == "validate":
            return cmd_validate(root)
        if args.command == "runnable":
            return cmd_runnable(root)
        if args.command == "fingerprint":
            return cmd_fingerprint(root, args.item_id)
        if args.command == "map-files":
            return cmd_map_files(root, args.files)
        if args.command == "invalidate":
            return cmd_invalidate(root, args.files, args.apply)
        if args.command == "start":
            return cmd_start(root, args.item_id, args.owner)
        if args.command == "record-pass":
            return cmd_record_pass(root, args.item_id, Path(args.payload), args.confirm_orchestrator)
        if args.command == "boundaries":
            return cmd_boundaries(root)
        if args.command == "secrets":
            return cmd_secrets(root)
        if args.command == "check-scopes":
            return cmd_check_scopes(root)
    except Exception as exc:  # noqa: BLE001 - CLI fail-closed
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
