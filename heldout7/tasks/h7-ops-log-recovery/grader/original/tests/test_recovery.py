import recovery


def test_empty_recovery(tmp_path):
    store = str(tmp_path / 'db')
    anchor = {'frontier': {'s': 0}, 'values': {'s': {}}, 'applied': []}
    assert recovery.initialize(store, anchor)['version'] == 0
    assert recovery.advance(store, 'first', 0, {'s': 0})['order'] == []
    assert recovery.inspect(store)['version'] == 1


def test_single_commit(tmp_path):
    store = str(tmp_path / 'db')
    recovery.initialize(store, {'frontier': {'s': 0}, 'values': {'s': {'k': '0'}}, 'applied': []})
    event = {'shard': 's', 'lsn': 1, 'txid': 't1', 'ordinal': 0, 'key': 'k', 'before': '0', 'after': '1'}
    seal = {'txid': 't1', 'outcome': 'commit', 'parents': [],
            'parts': {'s': {'lsns': [1], 'sha256': recovery.store.digest([event])}}}
    recovery.ingest(store, 'load', 0, {'events': [event], 'decisions': [seal]})
    result = recovery.advance(store, 'go', 1, {'s': 1})
    assert result['order'] == ['t1'] and result['values'] == {'s': {'k': '1'}}
