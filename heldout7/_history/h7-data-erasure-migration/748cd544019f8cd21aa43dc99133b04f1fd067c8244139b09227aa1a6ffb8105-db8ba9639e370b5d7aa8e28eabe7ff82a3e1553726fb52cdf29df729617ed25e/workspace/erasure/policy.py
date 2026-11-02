"""Rewrite policy deliveries."""


def current_policies(deliveries, at):
    """{node: delivery} for the policy revision in force at `at`."""
    seen, current = {}, {}
    for delivery in deliveries:
        if delivery['known'] > at:
            continue
        key = (delivery['node'], delivery['revision'])
        if key in seen and seen[key] != delivery:
            raise ValueError('conflicting policy revision %s/%s' % key)
        seen[key] = delivery
        if delivery['node'] not in current or delivery['revision'] > current[delivery['node']]['revision']:
            current[delivery['node']] = delivery
    return current
