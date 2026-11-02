"""Small summary-statistics helpers."""


def median(values):
    """Return the median of a non-empty sequence of numbers."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("median() arg is an empty sequence")
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2
