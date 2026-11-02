"""Progressive tier pricing (docs/billing_rules.md)."""


def progressive_millicents(units, tiers):
    """Exact millicents for `units` pooled usage units under ordered progressive tiers."""
    amount = 0; previous = 0; remaining = units
    for tier in tiers:
        take = remaining if tier['up_to'] is None else min(remaining, tier['up_to'] - previous)
        amount += take * tier['millicents']; remaining -= take
        if tier['up_to'] is not None:
            previous = tier['up_to']
        if remaining == 0:
            break
    return amount
