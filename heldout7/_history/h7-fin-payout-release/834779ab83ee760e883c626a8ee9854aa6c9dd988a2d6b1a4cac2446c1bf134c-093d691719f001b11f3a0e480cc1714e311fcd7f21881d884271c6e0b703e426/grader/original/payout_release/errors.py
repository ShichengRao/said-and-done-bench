class ReleaseError(ValueError):
    """The batch cannot be released as requested."""


class ReplayError(ReleaseError):
    """A schedule step is not allowed in the current replay state."""
