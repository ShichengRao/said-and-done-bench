"""Region, key and link approval policy."""


def eligible_links(dataset, config):
    """Approved links whose nodes are all in an allowed region and hold the dataset key."""
    result = []
    for link_id in sorted(set(dataset['approved_links'])):
        nodes = [config['nodes'][n] for n in config['links'][link_id]['nodes']]
        if all(n['region'] in dataset['regions'] and dataset['key'] in n['keys'] for n in nodes):
            result.append(link_id)
    return result
