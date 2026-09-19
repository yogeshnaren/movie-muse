"""Fail-closed platform errors."""


class PlatformError(RuntimeError):
    """Base error for application hosts."""


class LongFormUnavailableError(PlatformError):
    """Mobile hosts do not offer full long-form authoring."""


class DeepLinkError(PlatformError):
    """A deep link is malformed or targets a different golden identity."""


class CaptureConsentError(PlatformError):
    """On-set capture cannot start without visible consent."""


class StaticMockError(PlatformError):
    """Raised when a host would return canned state instead of a live workspace."""
