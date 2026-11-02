"""advance(): validate a sealed, causally closed, serializable cut and apply it in one transaction."""
import copy

from recovery.store import canonical, digest, finish, load, replayed, transaction


def advance(path, request_id, expected_version, target):
    payload = canonical(['advance', expected_version, target])
    with transaction(path) as db:
        state = load(db)
        previous = replayed(state, request_id, payload, expected_version)
        if previous is not None:
            return previous
        if set(target) != set(state['frontier']) or any(
                not isinstance(v, int) or isinstance(v, bool) or v < state['frontier'][k] for k, v in target.items()):
            raise ValueError('invalid target frontier')
        rows = []; edges = {}
        for shard in sorted(target):
            last = None
            for lsn in range(state['frontier'][shard] + 1, target[shard] + 1):
                event = state['events'].get(f'{shard}:{lsn}')
                if event is None:
                    raise ValueError(f'missing log event {shard}:{lsn}')
                rows.append(event); txid = event['txid']; edges.setdefault(txid, set())
                if last is not None and last != txid:
                    edges[txid].add(last)
                last = txid
        chosen = {e['txid'] for e in rows}
        selected = {t: [e for e in rows if e['txid'] == t] for t in chosen}
        for txid in sorted(chosen):
            if txid in state['processed'] or txid not in state['decisions']:
                raise ValueError(f'{txid} is already processed or has no decision')
            decision = state['decisions'][txid]; sealed = []
            for shard, part in decision['parts'].items():
                events = []
                for lsn in part['lsns']:
                    event = state['events'].get(f'{shard}:{lsn}')
                    if event is None or event['txid'] != txid:
                        raise ValueError(f'{txid} seal names a missing event')
                    if not state['frontier'][shard] < lsn <= target[shard]:
                        raise ValueError(f'{txid} crosses the requested cut')
                    events.append(event)
                if digest(events) != part['sha256']:
                    raise ValueError(f'{txid} seal digest mismatch')
                sealed.extend(events)
            buffered = [e for e in state['events'].values() if e['txid'] == txid]
            order = lambda e: (e['shard'], e['lsn'])
            if sorted(buffered, key=order) != sorted(sealed, key=order):
                raise ValueError(f'{txid} has unsealed events')
            if sorted(e['ordinal'] for e in sealed) != list(range(len(sealed))):
                raise ValueError(f'{txid} ordinals are not 0..N-1')
            if len(selected[txid]) != len(sealed):
                raise ValueError(f'{txid} is incomplete in the cut')
            for parent in decision['parents']:
                if state['processed'].get(parent) == 'commit':
                    continue
                if parent not in chosen or state['decisions'].get(parent, {}).get('outcome') != 'commit':
                    raise ValueError(f'{txid} depends on uncommitted {parent}')
                edges[txid].add(parent)
        order = []; pending = set(chosen)
        while pending:
            ready = sorted(t for t in pending if not edges[t] & pending)
            if not ready:
                raise ValueError('cut is not serializable')
            pending.remove(ready[0]); order.append(ready[0])
        for txid in order:
            decision = state['decisions'][txid]
            if decision['outcome'] == 'commit':
                for event in sorted(selected[txid], key=lambda e: e['ordinal']):
                    values = state['values'][event['shard']]
                    if values.get(event['key']) != event['before']:
                        raise ValueError(f'{txid} before-image mismatch on {event["shard"]}:{event["key"]}')
                    if event['after'] is None:
                        values.pop(event['key'], None)
                    else:
                        values[event['key']] = event['after']
            state['processed'][txid] = decision['outcome']
        state['frontier'] = copy.deepcopy(target)
        return finish(db, state, request_id, payload, {'order': order})
