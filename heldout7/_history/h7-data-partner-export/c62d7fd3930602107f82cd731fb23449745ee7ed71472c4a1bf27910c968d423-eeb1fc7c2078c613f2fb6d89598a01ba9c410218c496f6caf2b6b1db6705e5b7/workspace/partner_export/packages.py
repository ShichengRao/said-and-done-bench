"""Package authorization and utility-floor eligibility."""


def eligible(roster, packages, minimum_utility):
    """(eligible packages sorted by ID, excluded [{id, reason}] sorted by ID)."""
    usable, excluded = [], []
    for row in sorted(packages, key=lambda p: p['id']):
        queries = sorted((q['id'], roster.mask(q['members'])) for q in row['queries'])
        members = 0
        for _, mask in queries:
            members |= mask
        if not (row['approved'] and roster.consents(members)):
            excluded.append({'id': row['id'], 'reason': 'not_authorized'})
        elif row['utility'] < minimum_utility:
            excluded.append({'id': row['id'], 'reason': 'below_utility_floor'})
        else:
            usable.append({'id': row['id'], 'utility': row['utility'], 'queries': queries})
    return usable, excluded


def answer(package, world):
    """Ordered count tuple the package releases for a world key."""
    return tuple((world & mask).bit_count() for _, mask in package['queries'])
