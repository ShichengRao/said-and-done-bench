"""Splitting an amount in cents in proportion to weights (docs/allocation.md)."""


def allocate(total_cents, weights):
    """Split `total_cents` among `weights`, in proportion. Returns one share per weight, in cents.

    Largest remainders: everyone gets their exact share rounded down, and the
    cents left over go to the shares that lost the most, earliest first.
    """
    weights = list(weights)
    if not weights or any(weight < 0 for weight in weights) or sum(weights) == 0:
        raise ValueError(f'weights must be zero or more, with at least one positive: {weights}')
    total_weight = sum(weights)
    shares, remainders = [], []
    for weight in weights:
        share, remainder = divmod(total_cents * weight, total_weight)
        shares.append(share)
        remainders.append(remainder)
    leftover = total_cents - sum(shares)
    for index in sorted(range(len(weights)), key=lambda i: (-remainders[i], i))[:leftover]:
        shares[index] += 1
    return shares
