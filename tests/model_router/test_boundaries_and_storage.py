"""Import boundaries, no SQLite tables, and no provider SDK leaks."""

from __future__ import annotations

import ast
from pathlib import Path

from movie_muse.model_router.api import INDEX_META_KEY

FORBIDDEN_SDKS = (
    "openai",
    "anthropic",
    "google.generativeai",
    "cohere",
    "mistralai",
    "together",
    "groq",
    "boto3",
)


def _package_dir(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2] / "src" / "movie_muse" / Path(*parts)


def _iter_py(package: Path):
    return sorted(path for path in package.rglob("*.py") if path.is_file())


def test_model_router_imports_only_public_api_siblings() -> None:
    package = _package_dir("model_router")
    violations: list[tuple[str, str]] = []
    for source_path in _iter_py(package):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith("movie_muse."):
                continue
            parts = node.module.split(".")
            if len(parts) < 2 or parts[1] == "model_router":
                continue
            if parts[1] == "toolchain":
                continue
            if not node.module.endswith(".api"):
                violations.append((source_path.name, node.module))
    assert violations == []


def test_jobs_worker_document_revisions_do_not_import_provider_sdks() -> None:
    hits: list[tuple[str, str]] = []
    for name in ("jobs", "worker", "document", "revisions"):
        for source_path in _iter_py(_package_dir(name)):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                for module in modules:
                    if any(
                        module == sdk or module.startswith(f"{sdk}.") for sdk in FORBIDDEN_SDKS
                    ):
                        hits.append((str(source_path), module))
    assert hits == []


def test_model_router_does_not_import_vendor_sdks() -> None:
    hits: list[str] = []
    for source_path in _iter_py(_package_dir("model_router")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                if any(module == sdk or module.startswith(f"{sdk}.") for sdk in FORBIDDEN_SDKS):
                    hits.append(f"{source_path.name}:{module}")
    assert hits == []


def test_no_new_sqlite_tables(router_stack, request_factory) -> None:
    before = {
        str(row["name"])
        for row in router_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    router_stack.router.route(request_factory())
    after = {
        str(row["name"])
        for row in router_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert after == before
    digest = router_stack.workspace.store.get_meta(INDEX_META_KEY)
    assert digest is not None
    assert router_stack.workspace.store.blobs.exists(digest)
    assert "model_routes" not in after
    assert "model_quotes" not in after
