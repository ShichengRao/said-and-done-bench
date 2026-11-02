"""Merged identity groups."""


def merge_groups(records, merges):
    """Partition record IDs into merged groups using active merge links."""
    parent = {name: name for name in records}

    def root(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for link in merges.values():
        if link['active']:
            left, right = root(link['left']), root(link['right'])
            if left != right:
                parent[max(left, right)] = min(left, right)
    groups = {}
    for name in sorted(records):
        groups.setdefault(root(name), []).append(name)
    return {members[0]: members for members in groups.values()}


def group_load(members, records):
    return sum(records[name]['units'] for name in members)


def group_owners(members, records):
    owners = set(records[members[0]]['owners'])
    for name in members[1:]:
        owners &= set(records[name]['owners'])
    return sorted(owners)
