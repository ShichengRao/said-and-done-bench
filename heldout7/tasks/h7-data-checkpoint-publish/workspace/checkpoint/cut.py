"""Checkpoint selection across shards."""


def reach(export, logs):
    """Per shard, the end of the contiguous delivered prefix after the snapshot cut, capped at upper."""
    base, upper = export['snapshot']['cut'], export['request']['upper']
    result = {}
    for shard in sorted(base):
        offset = base[shard]
        while offset < upper[shard] and (shard, offset + 1) in logs:
            offset += 1
        result[shard] = offset
    return result


def covers(txn, cut):
    return all(cut[p['shard']] >= p['last'] for p in txn['parts'])


def consistent_cut(table, start):
    """Pull each shard back below transactions that cannot be published yet."""
    cut = dict(start)
    for txn in table.values():
        if txn['decision'] == 'unresolved':
            for part in txn['parts']:
                if cut[part['shard']] >= part['first']:
                    cut[part['shard']] = part['first'] - 1
    return cut
