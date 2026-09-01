"""Public surface of ``movie_muse.testkit``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.testkit.ast import ast_digest, derive_structural_facts, dump_ast
from movie_muse.testkit.bench import BenchRegistry, configuration_identity
from movie_muse.testkit.catalog import FixtureCatalog, load_rights_fixture, load_screenplay_document
from movie_muse.testkit.errors import (
    BenchError,
    ExpectedArtifactError,
    FixtureLicenseError,
    FixtureNotFoundError,
    NondeterminismError,
    RecordingError,
    TestkitError,
    UnapprovedGoldenUpdateError,
    UniversalScoreForbiddenError,
)
from movie_muse.testkit.expected import assert_expected_available, deferred_placeholder
from movie_muse.testkit.golden import (
    REVIEW_TOKEN_PLACEHOLDER,
    GoldenRegistry,
    approve_golden_update,
    payload_digest,
    sign_golden_update,
)
from movie_muse.testkit.nondeterminism import NondeterminismGuard
from movie_muse.testkit.paths import fixtures_root, screenplay_fixtures_root
from movie_muse.testkit.recordings import (
    list_recordings,
    load_adapter_result,
    load_recording,
    recording_to_adapter_result,
)
from movie_muse.testkit.seed import GoldenPathProject, load_golden_path_project
from movie_muse.testkit.types import (
    REQUIRED_PRODUCTION_EDGES,
    SYNTHETIC_AUDIENCE_DISCLAIMER,
    BenchReport,
    BenchTask,
    BlindedPreferenceLabel,
    DecodingSettings,
    EvaluationFamily,
    ExpectedArtifact,
    ExpectedKind,
    ExpectedStatus,
    FamilyScore,
    FixtureClass,
    FixtureManifest,
    FixtureRights,
    GoldenApproval,
    ScreenplayFixture,
    TaskConfiguration,
)

__all__ = [
    "REQUIRED_PRODUCTION_EDGES",
    "REVIEW_TOKEN_PLACEHOLDER",
    "SYNTHETIC_AUDIENCE_DISCLAIMER",
    "BenchError",
    "BenchRegistry",
    "BenchReport",
    "BenchTask",
    "BlindedPreferenceLabel",
    "DecodingSettings",
    "EvaluationFamily",
    "ExpectedArtifact",
    "ExpectedArtifactError",
    "ExpectedKind",
    "ExpectedStatus",
    "FamilyScore",
    "FixtureCatalog",
    "FixtureClass",
    "FixtureLicenseError",
    "FixtureManifest",
    "FixtureNotFoundError",
    "FixtureRights",
    "GoldenApproval",
    "GoldenPathProject",
    "GoldenRegistry",
    "NondeterminismError",
    "NondeterminismGuard",
    "RecordingError",
    "ScreenplayFixture",
    "TaskConfiguration",
    "TestkitError",
    "UnapprovedGoldenUpdateError",
    "UniversalScoreForbiddenError",
    "approve_golden_update",
    "assert_expected_available",
    "ast_digest",
    "configuration_identity",
    "deferred_placeholder",
    "derive_structural_facts",
    "dump_ast",
    "fixtures_root",
    "list_recordings",
    "load_adapter_result",
    "load_golden_path_project",
    "load_recording",
    "load_rights_fixture",
    "load_screenplay_document",
    "payload_digest",
    "recording_to_adapter_result",
    "screenplay_fixtures_root",
    "sign_golden_update",
]
