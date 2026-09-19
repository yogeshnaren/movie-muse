"""Fail-closed operations errors."""


class OperationsError(RuntimeError):
    """Base operations error."""


class CostCapError(OperationsError):
    """Declared spend would exceed the cost cap."""


class SbomError(OperationsError):
    """SBOM is missing or contains a denied dependency."""


class IncidentError(OperationsError):
    """Incident drill failed or is incomplete."""
