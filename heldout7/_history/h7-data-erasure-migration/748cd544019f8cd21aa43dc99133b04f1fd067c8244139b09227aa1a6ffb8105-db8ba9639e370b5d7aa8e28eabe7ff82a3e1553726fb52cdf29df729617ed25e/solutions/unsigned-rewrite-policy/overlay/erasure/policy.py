"""Rewrite policy deliveries."""


def current_policies(deliveries, at):
    """{node: delivery} for the highest approved revision already effective at `at`.

    Deliveries not yet known at `at` are ignored. Conflicting visible deliveries for one
    (node, revision) are an error even when they are drafts or not yet effective.
    """
    seen, current = {}, {}
    for delivery in deliveries:
        if delivery['known'] > at:
            continue
        key = (delivery['node'], delivery['revision'])
        if key in seen and seen[key] != delivery:
            raise ValueError('conflicting policy revision %s/%s' % key)
        seen[key] = delivery
    for delivery in seen.values():
        if delivery['effective_at'] > at:
            continue
        node = delivery['node']
        if node not in current or delivery['revision'] > current[node]['revision']:
            current[node] = delivery
    return current
