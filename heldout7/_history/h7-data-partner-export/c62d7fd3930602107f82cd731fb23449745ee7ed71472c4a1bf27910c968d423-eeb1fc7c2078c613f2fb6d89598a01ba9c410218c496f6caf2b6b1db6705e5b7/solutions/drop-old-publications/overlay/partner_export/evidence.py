"""Public prior releases, private snapshot validation and the public baseline worlds."""
MAX_WORLDS = 12


def snapshot_keys(roster, snapshots):
    return {epoch: sum(snapshots[epoch][name] << i for i, name in enumerate(roster.people)) for epoch in ('old', 'current')}


def prior_rows(roster, prior):
    return [(row['epoch'], roster.mask(row['members']), row['count']) for row in prior]


def validate(actual, rows, max_changes):
    if (actual['old'] ^ actual['current']).bit_count() > max_changes:
        raise ValueError('snapshots exceed the transition bound')
    if any((actual[epoch] & mask).bit_count() != count for epoch, mask, count in rows):
        raise ValueError('snapshots contradict a prior release')


def baseline(roster, rows, max_changes):
    """Distinct current world keys consistent with every prior release and the transition bound."""
    n = len(roster.people)
    old = list(range(1 << n))  # earlier-epoch releases treated as superseded
    worlds = [v for v in range(1 << n)
              if all((v & m).bit_count() == c for e, m, c in rows if e == 'current')
              and any((v ^ o).bit_count() <= max_changes for o in old)]
    if len(worlds) > MAX_WORLDS:
        raise ValueError('more than %d baseline worlds' % MAX_WORLDS)
    return worlds
