"""Splitting an amount in cents in proportion to weights (docs/allocation.md)."""


def allocate(total_cents, weights):
    """Split `total_cents` among `weights`, in proportion. Returns one share per weight, in cents."""
    total_weight = sum(weights)
    shares = [total_cents * weight // total_weight for weight in weights]
    shares[-1] += total_cents - sum(shares)
    return shares
