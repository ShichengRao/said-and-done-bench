"""ingest(): buffer exported log events and transaction decisions."""
import copy

from recovery.store import canonical, finish, load, replayed, transaction


def ingest(path, request_id, expected_version, batch):
    payload = canonical(['ingest', expected_version, batch])
    with transaction(path) as db:
        state = load(db)
        previous = replayed(state, request_id, payload, expected_version)
        if previous is not None:
            return previous
        anchor = state['anchor']
        for event in batch['events']:
            shard, lsn = event['shard'], event['lsn']
            if (shard not in state['frontier'] or not isinstance(lsn, int) or isinstance(lsn, bool)
                    or lsn <= anchor['frontier'][shard] or event['ordinal'] < 0 or event['txid'] in anchor['applied']):
                raise ValueError('invalid event coordinate')
            state['events'][f'{shard}:{lsn}'] = copy.deepcopy(event)  # latest export wins
        for decision in batch['decisions']:
            if (decision['outcome'] not in ('commit', 'abort') or not decision['parts'] or decision['txid'] in anchor['applied']
                    or len(set(decision['parents'])) != len(decision['parents'])):
                raise ValueError('invalid decision')
            for shard, part in decision['parts'].items():
                if (shard not in state['frontier'] or not part['lsns'] or part['lsns'] != sorted(set(part['lsns']))
                        or min(part['lsns']) <= anchor['frontier'][shard]):
                    raise ValueError('invalid seal manifest')
            if decision['txid'] in state['decisions'] and state['decisions'][decision['txid']] != decision:
                raise ValueError(f"conflicting decision for {decision['txid']}")
            state['decisions'][decision['txid']] = copy.deepcopy(decision)
        return finish(db, state, request_id, payload, {'ingested': True})
