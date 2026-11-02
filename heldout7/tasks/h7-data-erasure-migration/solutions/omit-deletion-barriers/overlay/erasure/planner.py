"""Rewrite planning: clean clones, live redirects and purge sets."""


class PlanError(Exception):
    """No permitted rewrite plan removes the requested data safely."""


def clean_views(views, is_erased):
    """Original map of each node with directly erased payloads replaced by tombstones."""
    return {name: {key: row for key, row in view.items() if not is_erased(row)}
            for name, view in views.items()}


def materialize(selected, nodes, heads, clean, dirty_nodes, policies, held):
    """Plan for rewriting `selected`, or None when it leaves erased data live or loses other rows."""
    live, memo = set(), {}

    def effective(name):
        if name in memo:
            return memo[name]
        if name in selected:
            memo[name] = clean[name]
            return memo[name]
        live.add(name)
        merged = {}
        for parent in nodes[name]['parents']:
            merged.update(effective(parent))
        merged.update({row['key']: row for row in nodes[name]['rows']})
        memo[name] = merged
        return merged

    views = []
    for obj, root in sorted(heads.items()):
        actual = {k: r for k, r in effective(root).items() if not r['deleted']}
        wanted = {k: r for k, r in clean[root].items() if not r['deleted']}
        if actual != wanted:
            return None
        views.append({'object': obj, 'rows': [actual[k] for k in sorted(actual)]})
    if live & dirty_nodes:
        return None
    return {'cost': sum(policies[n]['cost'] for n in selected),
            'rewrites': [{'original': n, 'clone': 'rewrite:' + n, 'cost': policies[n]['cost'], 'parents': [],
                          'rows': [clean[n][k] for k in sorted(clean[n])]} for n in sorted(selected)],
            'live_roots': [{'object': o, 'node': 'rewrite:' + n if n in selected else n} for o, n in sorted(heads.items())],
            'live_originals': sorted(live), 'purge_nodes': sorted(set(nodes) - live - set(held)), 'logical_views': views}


def choose(nodes, heads, clean, dirty_nodes, policies, held):
    """Least-cost safe plan over every subset of currently permitted nodes.

    Shared ancestors are candidates as well as live roots, so one clean clone can
    serve several heads. Ties: lowest cost, fewest rewrites, smallest sorted IDs.
    """
    missing = sorted(set(nodes) - set(policies))
    if missing:
        raise PlanError('no current rewrite policy for %s' % ', '.join(missing))
    allowed = sorted(n for n in nodes if policies[n]['allow'])
    best = None
    for mask in range(1 << len(allowed)):
        selected = {n for i, n in enumerate(allowed) if mask >> i & 1}
        rank = (sum(policies[n]['cost'] for n in selected), len(selected), sorted(selected))
        if best is not None and rank >= best[0]:
            continue
        plan = materialize(selected, nodes, heads, clean, dirty_nodes, policies, held)
        if plan is not None:
            best = (rank, plan)
    if best is None:
        raise PlanError('no permitted rewrite plan removes the requested data safely')
    return best[1]
