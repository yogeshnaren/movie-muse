"""Fail-closed privacy errors."""


class PrivacyError(RuntimeError):
    """Base privacy error."""


class ErasedError(PrivacyError):
    """Subject was deleted and must not be read."""


class TrainingConsentError(PrivacyError):
    """Training on user content is off unless explicitly opted in."""


class CrossUserCacheError(PrivacyError):
    """Provider prompt cache must not span users."""


class RetentionError(PrivacyError):
    """A record is past its retention window."""
