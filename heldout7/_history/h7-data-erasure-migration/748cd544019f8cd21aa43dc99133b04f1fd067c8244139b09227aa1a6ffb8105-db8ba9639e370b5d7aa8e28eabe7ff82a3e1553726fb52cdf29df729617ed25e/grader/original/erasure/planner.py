"""Rewrite planning: clean clones, live redirects and purge sets."""


class PlanError(Exception):
    """No permitted rewrite plan removes the requested data safely."""


def clean_views(views, is_erased):
    """Original map of each node with directly erased payloads replaced by tombstones."""
    return {name: {key: ({'key': key, 'deleted': True} if is_erased(row) else row) for key, row in view.items()}
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
    """Prototype: rewrite every live root that physically reaches erased data."""
    def reaches(name):
        return name in dirty_nodes or any(reaches(p) for p in nodes[name]['parents'])
    selected = {root for root in heads.values() if reaches(root)}
    denied = sorted(n for n in selected if not policies[n]['allow'])
    if denied:
        raise PlanError('rewrite not permitted for %s' % ', '.join(denied))
    plan = materialize(selected, nodes, heads, clean, dirty_nodes, policies, held)
    if plan is None:
        raise PlanError('root rewrites do not remove the requested data safely')
    return plan
