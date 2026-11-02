"""Outage-profile checks for a set of dataset topologies."""


def profile_problems(selection, config, profile):
    """Problems with `selection` ({dataset_id: link_id}) under one outage profile."""
    datasets = {d['id']: d for d in config['datasets']}
    down = set(profile['down'])
    problems = []
    load = {}
    for dataset_id, link_id in selection.items():
        nodes = config['links'][link_id]['nodes']
        alive = [n for n in nodes if n not in down]
        if len(alive) < datasets[dataset_id]['replicas_required']:
            problems.append('%s keeps %d replicas in %s' % (dataset_id, len(alive), profile['id']))
        share = datasets[dataset_id]['units'] / len(nodes)
        for node in alive:
            load[node] = load.get(node, 0) + share
    for node, units in sorted(load.items()):
        if units > profile['leases'][node]:
            problems.append('node %s needs %s units in %s (lease %s)' % (node, units, profile['id'], profile['leases'][node]))
    return problems
