class BuildGraphError(Exception):
    """Something about the packages that makes a build order impossible."""


class UnknownDependency(BuildGraphError):
    pass


class UnknownPackage(BuildGraphError):
    pass


class CycleError(BuildGraphError):
    pass


class BadPackage(BuildGraphError):
    pass
