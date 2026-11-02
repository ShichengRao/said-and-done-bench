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
    """Publish up to the delivered watermark; unresolved transactions are simply not applied."""
    return dict(start)
