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
    """Greatest valid checkpoint at or below `start`.

    A transaction touched by the cut must be fully covered, finalized and have all its
    dependencies fully covered; otherwise every shard it touches is pulled back below it.
    Repeat until nothing changes, since pulling back one shard can uncover other partial
    or dependent transactions. Each step only lowers offsets, so the fixed point is the
    componentwise greatest valid cut.
    """
    cut = dict(start)
    while True:
        lowered = dict(cut)
        for txn in table.values():
            touched = any(cut[p['shard']] >= p['first'] for p in txn['parts'])
            valid = (txn['decision'] != 'unresolved' and covers(txn, cut))
            if touched and not valid:
                for part in txn['parts']:
                    if cut[part['shard']] >= part['first']:
                        lowered[part['shard']] = min(lowered[part['shard']], part['first'] - 1)
        if lowered == cut:
            return cut
        cut = lowered
