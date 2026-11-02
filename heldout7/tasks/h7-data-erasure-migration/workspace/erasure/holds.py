"""Active evidence holds and the original nodes they retain."""


def retained(nodes, holds, at):
    """{node: [hold IDs]} for every original ancestor of an active hold."""
    result = {}
    for hold in holds:
        if not (hold['from'] <= at and (hold['until'] is None or at < hold['until'])):
            continue
        if hold['node'] not in nodes:
            raise ValueError('active hold %s names a missing node' % hold['id'])
        stack, seen = [hold['node']], set()
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            result.setdefault(name, []).append(hold['id'])
            stack.extend(nodes[name]['parents'])
    return {name: sorted(ids) for name, ids in sorted(result.items())}
