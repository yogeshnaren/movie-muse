"""Fail-closed observability errors."""


class ObservabilityError(RuntimeError):
    """Base observability error."""


class ContentLeakageError(ObservabilityError):
    """Telemetry would have carried screenplay or secret content."""


class SloBreachError(ObservabilityError):
    """A declared SLO is below its target."""
