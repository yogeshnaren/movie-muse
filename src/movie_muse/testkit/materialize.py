"""Write committed fixture files from deterministic builders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from movie_muse.testkit.ast import dump_ast
from movie_muse.testkit.builders import (
    LICENSE_BODY,
    BuiltFixture,
    all_screenplay_fixtures,
    build_feature_complete_harbor,
)
from movie_muse.testkit.expected import deferred_placeholder
from movie_muse.testkit.ids import IdMint
from movie_muse.testkit.paths import (
    bench_root,
    fixtures_root,
    golden_path_root,
    recordings_root,
    rights_fixtures_root,
    screenplay_fixtures_root,
)
from movie_muse.testkit.types import ExpectedKind
from movie_muse.toolchain import repo_root


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_screenplay(root: Path, built: BuiltFixture) -> None:
    directory = screenplay_fixtures_root(root) / built.fixture_id
    directory.mkdir(parents=True, exist_ok=True)
    _dump_json(directory / "document.json", built.document.to_dict())
    (directory / "LICENSE.md").write_text(LICENSE_BODY, encoding="utf-8")
    _dump_yaml(
        directory / "MANIFEST.yaml",
        {
            "id": built.fixture_id,
            "class": built.fixture_class.value,
            "title": built.title,
            "edges": list(built.edges),
            "license_file": "LICENSE.md",
            "rights_file": "rights.yaml",
        },
    )
    _dump_yaml(directory / "rights.yaml", built.rights)
    expected = directory / "expected"
    expected.mkdir(parents=True, exist_ok=True)
    _dump_json(expected / "ast.json", dump_ast(built.document))
    _dump_json(expected / "layout.json", deferred_placeholder(ExpectedKind.LAYOUT).to_dict())
    _dump_json(expected / "film_ir.json", deferred_placeholder(ExpectedKind.FILM_IR).to_dict())


def _write_rights(root: Path) -> None:
    mint = IdMint(2000)
    licensed = {
        "source_id": mint.prefixed("src"),
        "title": "Licensed golden-path corpus",
        "classification": "licensed",
        "license": "CC0-1.0",
        "license_summary": "CC0-1.0 original Movie Muse fixture",
        "license_expiry": "2099-01-01T00:00:00Z",
        "consent": "explicit_fixture_dedication",
        "origin": "original_authored_for_movie_muse",
        "allow_training": False,
        "permitted_uses": ["retrieval", "citation", "generation", "export_disclosure"],
    }
    unlicensed = {
        "source_id": mint.prefixed("src"),
        "title": "Unlicensed scrape (blocked)",
        "classification": "unlicensed",
        "license": "none",
        "consent": "none",
        "origin": "negative_fixture_not_for_use",
        "allow_training": False,
        "permitted_uses": [],
    }
    directory = rights_fixtures_root(root)
    _dump_yaml(directory / "licensed.yaml", licensed)
    _dump_yaml(directory / "unlicensed.yaml", unlicensed)


def _recording(
    *,
    capability: str,
    output: dict[str, Any],
    model_version: str,
) -> dict[str, Any]:
    return {
        "capability": capability,
        "live": False,
        "network": False,
        "model_version": model_version,
        "input_tokens": 8,
        "output_tokens": 16,
        "actual_cost": 0.0,
        "method": "deterministic_fixture",
        "assumptions": ["fixture", "no_network", "not_a_human_sample"],
        "uncertainty": "deterministic_fixture",
        "output": output,
    }


def _write_recordings(root: Path) -> None:
    directory = recordings_root(root)
    _dump_json(
        directory / "extract_structure.json",
        _recording(
            capability="extract_structure",
            model_version="double-extract-v1",
            output={
                "entities": [{"name": "Jordan", "kind": "character"}],
                "method": "deterministic_fixture",
                "assumptions": ["fixture", "no_network", "not_a_human_sample"],
                "uncertainty": "deterministic_fixture",
            },
        ),
    )
    _dump_json(
        directory / "generate_text.json",
        _recording(
            capability="generate_text",
            model_version="double-text-v1",
            output={
                "text": "INT. HARBOR OFFICE - NIGHT\nRain needles the glass.",
                "method": "deterministic_fixture",
                "assumptions": ["fixture", "no_network", "not_a_human_sample"],
                "uncertainty": "deterministic_fixture",
            },
        ),
    )
    _dump_json(
        directory / "retrieve.json",
        _recording(
            capability="retrieve",
            model_version="double-retrieve-v1",
            output={
                "passages": ["Permitted local fixture passage."],
                "method": "deterministic_fixture",
                "assumptions": ["fixture", "no_network", "not_a_human_sample"],
                "uncertainty": "deterministic_fixture",
            },
        ),
    )


def _write_bench(root: Path) -> None:
    harbor = build_feature_complete_harbor()
    config_a = {
        "model": "local-extract-v1",
        "prompt": "extract_scenes.v1",
        "context_strategy": "current_revision_only",
        "tools": ["schema_validate"],
        "decoding": {"temperature": 0.0, "top_p": 1.0, "seed": 0},
        "schema": "structural_fact",
    }
    config_b = {
        "model": "local-extract-v1",
        "prompt": "extract_scenes.v2_longer_context",
        "context_strategy": "revision_plus_notes",
        "tools": ["schema_validate", "rights_filter"],
        "decoding": {"temperature": 0.0, "top_p": 1.0, "seed": 0},
        "schema": "structural_fact",
    }
    from movie_muse.testkit.bench import configuration_identity
    from movie_muse.testkit.types import TaskConfiguration

    identity_a = configuration_identity(TaskConfiguration.from_dict(config_a))
    identity_b = configuration_identity(TaskConfiguration.from_dict(config_b))
    payload = {
        "tasks": [
            {
                "id": "extract_scenes_small",
                "family": "objective_ground_truth",
                "fixture_id": "small_kitchen",
                "configuration": config_a,
            },
            {
                "id": "blinded_rewrite_preference",
                "family": "blinded_human_preference",
                "fixture_id": harbor.fixture_id,
                "configuration": config_a,
                "labels": [
                    {
                        "rater_id": "rater_blind_001",
                        "winner_configuration_id": identity_a,
                        "loser_configuration_id": identity_b,
                        "blinded": True,
                        "notes": "Labels are configuration identities, not model brands.",
                    }
                ],
            },
            {
                "id": "observed_scene_authoring_utility",
                "family": "observed_workflow_utility",
                "fixture_id": harbor.fixture_id,
                "configuration": config_a,
                "utility_metric": "scenes_authored_per_correction_minute",
                "disclaimer": (
                    "Observed editor workflow utility. Synthetic audiences are hypotheses, "
                    "not human samples."
                ),
            },
        ]
    }
    _dump_yaml(bench_root(root) / "tasks.yaml", payload)


def _write_golden_path(root: Path) -> None:
    harbor = build_feature_complete_harbor()
    extras = harbor.extras
    _dump_yaml(
        golden_path_root(root) / "MANIFEST.yaml",
        {
            "id": "golden_path_harbor",
            "fixture_id": harbor.fixture_id,
            "organization_id": extras["organization_id"],
            "owner_actor_id": extras["owner_actor_id"],
            "branch_id": extras["branch_id"],
            "created_at": extras["created_at"],
            "project_title": extras["project_title"],
            "owner_display_name": extras["owner_display_name"],
            "organization_name": extras["organization_name"],
            "offline": True,
        },
    )
    (golden_path_root(root) / "LICENSE.md").write_text(LICENSE_BODY, encoding="utf-8")


def _write_root_license(root: Path) -> None:
    (fixtures_root(root) / "LICENSE.md").write_text(
        LICENSE_BODY
        + "\nEach screenplay fixture directory repeats this dedication and a rights.yaml.\n",
        encoding="utf-8",
    )


def materialize(root: Path | None = None) -> None:
    resolved = root or repo_root()
    fixtures_root(resolved).mkdir(parents=True, exist_ok=True)
    _write_root_license(resolved)
    for built in all_screenplay_fixtures():
        _write_screenplay(resolved, built)
    _write_rights(resolved)
    _write_recordings(resolved)
    _write_bench(resolved)
    _write_golden_path(resolved)


if __name__ == "__main__":
    materialize()
