"""Fail-closed errors for the fixture catalog and MovieMuse Bench harness."""

from __future__ import annotations


class TestkitError(RuntimeError):
    """Base error for golden fixtures and the evaluation harness."""


class FixtureNotFoundError(TestkitError):
    """A requested fixture id is not present in the catalog."""


class FixtureLicenseError(TestkitError):
    """A fixture is missing recorded license, consent, or permitted-use metadata."""


class UnapprovedGoldenUpdateError(TestkitError):
    """An attempt to overwrite a golden file lacked explicit review approval."""


class NondeterminismError(TestkitError):
    """Repeated loads or hashes of the same fixture did not agree."""


class ExpectedArtifactError(TestkitError):
    """An expected artifact is missing, deferred when required, or falsely current."""


class UniversalScoreForbiddenError(TestkitError):
    """MovieMuse Bench refuses to collapse evaluation families into one score."""


class BenchError(TestkitError):
    """A benchmark task, configuration, or score is invalid."""


class RecordingError(TestkitError):
    """A provider recording is missing, live, or not double-adapter compatible."""
