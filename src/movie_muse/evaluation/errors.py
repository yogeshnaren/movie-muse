"""Fail-closed evaluation errors."""


class EvaluationError(RuntimeError):
    """Base evaluation error."""


class BaselineError(EvaluationError):
    """Local or fine-tuned route missed a declared quality/safety baseline."""


class LeverageError(EvaluationError):
    """Creator Leverage Ratio is not positive."""


class PopulationClaimError(EvaluationError):
    """Synthetic evaluation output was described as a human population sample."""
