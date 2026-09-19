"""Fail-closed security errors."""


class SecurityError(RuntimeError):
    """Base security error."""


class OpenHighSeverityError(SecurityError):
    """HIGH/CRITICAL findings remain open."""


class IntegrityError(SecurityError):
    """Sealed payload MAC did not verify."""


class KeyUnavailableError(SecurityError):
    """BYOK/customer key or private route is not configured."""
