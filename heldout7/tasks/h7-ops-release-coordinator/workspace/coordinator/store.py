import copy


class ResourceStore:
    """In-memory copy of the resource registers used while a batch is coordinated."""

    def __init__(self, values):
        self._values = copy.deepcopy(values)

    def compare_and_set(self, expected, writes):
        """Atomically compare every expected value and apply all writes only if they all match."""
        for name in list(expected) + list(writes):
            if name not in self._values:
                raise KeyError(name)
        if any(self._values[name] != value for name, value in expected.items()):
            return False
        self._values.update(writes)
        return True

    def snapshot(self):
        return copy.deepcopy(self._values)
