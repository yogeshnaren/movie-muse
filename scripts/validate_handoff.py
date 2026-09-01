#!/usr/bin/env python3
"""Fail-closed static validation for the Movie Muse V2 handoff package."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - explicit bootstrap failure
    raise SystemExit("ERROR: PyYAML is required to validate the handoff") from exc

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - explicit bootstrap failure
    raise SystemExit("ERROR: jsonschema is required to validate the handoff") from exc


ROOT = Path(__file__).resolve().parents[1]
DAG_PATH = ROOT / "dependency_dag.yaml"
MANIFEST_PATH = ROOT / "movie_muse_build_status.yaml"
PLAN_PATH = ROOT / "MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md"
ARCH_PATH = ROOT / "MOVIE_MUSE_V2_ARCHITECTURE.md"
PROMPT_PATH = ROOT / "CURSOR_MASTER_EXECUTION_PROMPT.md"
TRACE_PATH = ROOT / "FEATURE_TRACEABILITY_AND_GAP_REVIEW.md"
SCHEMA_PATH = ROOT / "schemas" / "build-status.schema.json"
EXPECTED_IDS = [f"MM-{number:03d}" for number in range(1, 48)]
STATUSES = {"NOT_STARTED", "IN_PROGRESS", "PASS", "FAIL", "BLOCKED_EXTERNAL", "STALE"}
SENTINEL = "MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.name}: {exc}")


def unique_index(records, label):
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        fail(f"duplicate IDs in {label}")
    return {record["id"]: record for record in records}


def assert_acyclic(nodes):
    indegree = {node_id: len(node["depends_on"]) for node_id, node in nodes.items()}
    reverse = defaultdict(list)
    for node_id, node in nodes.items():
        for dep in node["depends_on"]:
            reverse[dep].append(node_id)
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    seen = []
    while queue:
        current = queue.popleft()
        seen.append(current)
        for dependent in sorted(reverse[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    if len(seen) != len(nodes):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        fail(f"dependency graph contains a cycle involving {cyclic}")


def main() -> None:
    required = [DAG_PATH, MANIFEST_PATH, PLAN_PATH, ARCH_PATH, PROMPT_PATH, TRACE_PATH, SCHEMA_PATH]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required files: {missing}")

    dag = load_yaml(DAG_PATH)
    manifest = load_yaml(MANIFEST_PATH)
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(manifest)
    except Exception as exc:
        fail(f"manifest/schema validation failed: {exc}")

    if dag.get("schema_version") != "2.0" or manifest.get("schema_version") != "2.0":
        fail("schema versions must both be 2.0")
    if dag.get("package_version") != manifest.get("package_version"):
        fail("package versions differ")

    dag_nodes = unique_index(dag.get("nodes", []), "DAG")
    items = unique_index(manifest.get("items", []), "manifest")
    if list(sorted(dag_nodes)) != EXPECTED_IDS:
        fail("DAG must contain exactly MM-001 through MM-047")
    if list(sorted(items)) != EXPECTED_IDS:
        fail("manifest must contain exactly MM-001 through MM-047")

    for node_id, node in dag_nodes.items():
        dependencies = node.get("depends_on")
        if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)):
            fail(f"{node_id} has invalid or duplicate dependencies")
        if node_id in dependencies:
            fail(f"{node_id} depends on itself")
        unknown = sorted(set(dependencies) - set(dag_nodes))
        if unknown:
            fail(f"{node_id} has unknown dependencies: {unknown}")
        item = items[node_id]
        if item.get("title") != node.get("title"):
            fail(f"{node_id} title differs between DAG and manifest")
        if item.get("milestone") != node.get("milestone"):
            fail(f"{node_id} milestone differs between DAG and manifest")
        if item.get("depends_on") != dependencies:
            fail(f"{node_id} dependencies differ between DAG and manifest")
        if item.get("status") not in STATUSES:
            fail(f"{node_id} has invalid status")
        if not item.get("scope_keys"):
            fail(f"{node_id} has no scope keys")

    assert_acyclic(dag_nodes)
    expected_final = EXPECTED_IDS[:-1]
    if dag_nodes["MM-047"]["depends_on"] != expected_final:
        fail("MM-047 must depend directly on MM-001 through MM-046")

    for node_id, item in items.items():
        status = item["status"]
        if status == "PASS":
            record = item.get("pass_record")
            required_record = {"verification_commit", "input_fingerprint", "commands", "evidence", "completed_at_utc", "independent_verifier"}
            if not isinstance(record, dict) or not required_record.issubset(record):
                fail(f"{node_id} PASS is missing its complete pass_record")
            if record.get("independent_verifier", {}).get("result") != "PASS":
                fail(f"{node_id} PASS lacks independent verifier PASS")
            for dep in item["depends_on"]:
                if items[dep]["status"] != "PASS":
                    fail(f"{node_id} is PASS but prerequisite {dep} is not PASS")
        if status == "BLOCKED_EXTERNAL" and not item.get("blocker"):
            fail(f"{node_id} is BLOCKED_EXTERNAL without blocker details")
        if status not in {"PASS", "BLOCKED_EXTERNAL"} and item.get("blocker"):
            fail(f"{node_id} has blocker details but status is {status}")

    gate_ids = set()
    for gate in manifest.get("external_gates", []):
        gate_id = gate.get("id")
        if gate_id in gate_ids:
            fail(f"duplicate external gate {gate_id}")
        gate_ids.add(gate_id)
        if gate.get("owner_item") not in items:
            fail(f"external gate {gate_id} has unknown owner")
        if gate.get("status") == "PASS" and not gate.get("evidence"):
            fail(f"external gate {gate_id} is PASS without evidence")

    digest = hashlib.sha256(DAG_PATH.read_bytes()).hexdigest()
    recorded_digest = manifest.get("dag_sha256")
    if recorded_digest != digest:
        fail(f"manifest dag_sha256 is {recorded_digest!r}; expected {digest}")

    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    plan_headings = re.findall(r"^#### (MM-[0-9]{3}) (.+)$", plan_text, re.MULTILINE)
    plan_ids = sorted({node_id for node_id, _ in plan_headings})
    if plan_ids != EXPECTED_IDS:
        fail("build plan headings must contain exactly MM-001 through MM-047")
    if len(plan_headings) != 47:
        fail("each work-package ID must occur exactly once as a build-plan heading")
    for node_id, title in plan_headings:
        if dag_nodes[node_id]["title"] != title:
            fail(f"{node_id} title differs between build plan and DAG")
    if SENTINEL not in plan_text or SENTINEL not in PROMPT_PATH.read_text(encoding="utf-8"):
        fail("final PASS sentinel is inconsistent or missing")
    version_marker = f"Version: `{manifest['package_version']}`"
    if version_marker not in ARCH_PATH.read_text(encoding="utf-8"):
        fail("architecture version is missing or inconsistent")
    if version_marker not in plan_text or version_marker not in TRACE_PATH.read_text(encoding="utf-8"):
        fail("build-plan or traceability version is missing or inconsistent")

    required_sequences = [
        ("MM-009", "MM-018"),
        ("MM-012", "MM-013"),
        ("MM-012", "MM-018"),
        ("MM-007", "MM-032"),
        ("MM-007", "MM-036"),
        ("MM-007", "MM-039"),
        ("MM-007", "MM-043"),
        ("MM-035", "MM-037"),
        ("MM-037", "MM-038"),
        ("MM-038", "MM-039"),
    ]

    def reaches(prerequisite, dependent):
        stack = list(dag_nodes[dependent]["depends_on"])
        visited = set()
        while stack:
            current = stack.pop()
            if current == prerequisite:
                return True
            if current not in visited:
                visited.add(current)
                stack.extend(dag_nodes[current]["depends_on"])
        return False

    for prerequisite, dependent in required_sequences:
        if not reaches(prerequisite, dependent):
            fail(f"required sequencing missing: {prerequisite} before {dependent}")

    if manifest.get("overall_status") == "PASS":
        incomplete = [node_id for node_id, item in items.items() if item["status"] != "PASS"]
        blocked_gates = [
            gate["id"]
            for gate in manifest.get("external_gates", [])
            if gate.get("required_for_final") and gate.get("status") != "PASS"
        ]
        if incomplete or blocked_gates:
            fail(f"overall PASS has incomplete items={incomplete} external_gates={blocked_gates}")

    support_files = [
        ROOT / "AGENTS.md",
        ROOT / ".cursor" / "rules" / "00-movie-muse-core.mdc",
        ROOT / ".cursor" / "rules" / "10-verification-and-status.mdc",
        ROOT / ".cursor" / "agents" / "implementer.md",
        ROOT / ".cursor" / "agents" / "independent-verifier.md",
        ROOT / "DEPENDENCY_GRAPH.md",
        ROOT / "FEATURE_TRACEABILITY_AND_GAP_REVIEW.md",
        ROOT / "CURSOR_AUTONOMOUS_RUNBOOK.md",
        ROOT / "QA_REPORT.md",
        ROOT / "README_HANDOFF.md",
        ROOT / "scripts" / "verify_all.sh",
    ]
    support_missing = [str(path.relative_to(ROOT)) for path in support_files if not path.is_file()]
    if support_missing:
        fail(f"missing agent/handoff support files: {support_missing}")

    trace_text = TRACE_PATH.read_text(encoding="utf-8")
    trace_rows = re.findall(r"^\| (1[0-4]|[1-9]) \|", trace_text, re.MULTILINE)
    if sorted({int(number) for number in trace_rows}) != list(range(1, 15)):
        fail("traceability matrix must cover requested features 1 through 14 exactly")
    required_v21_terms = [
        "ProjectEvent",
        "CRDT",
        "AI-off",
        "SceneSpace",
        "MovieMuse Bench",
        "Creator Leverage",
        "budget maturity",
        "Integration Mesh",
    ]
    missing_terms = [term for term in required_v21_terms if term not in trace_text]
    if missing_terms:
        fail(f"V2.1 traceability is missing corrections: {missing_terms}")
    gates = {gate["id"] for gate in manifest.get("external_gates", [])}
    if "EXT-INSURANCE-PARTNER" not in gates:
        fail("insurance specialist handoff gate is missing")

    print(f"HANDOFF_VALIDATION=PASS packages={len(items)} dag_sha256={digest}")


if __name__ == "__main__":
    main()
