from refund_worker import service as r

CAPTURES = [dict(id='c1', merchant='m', currency='USD', captured_cents=100, refund_until=20)]


def test_empty_store(tmp_path):
    p = str(tmp_path / 'db'); assert r.initialize(p, [])['clock'] == 0
    assert r.apply(p, {'operation_id': 'tick', 'at': 1, 'kind': 'tick'})['result'] == 'ticked'


def test_reserve_holds_and_expires(tmp_path):
    p = str(tmp_path / 'db'); r.initialize(p, CAPTURES)
    q = dict(operation_id='res', at=1, kind='reserve', refund='x', merchant='m', currency='USD', cents=30, until=5, candidates=['c1'])
    out = r.apply(p, q)
    assert out['result'] == 'reserved' and r.apply(p, q) == out
    assert r.snapshot(p)['captures'][0]['held_cents'] == 30
    r.apply(p, dict(operation_id='t', at=5, kind='tick'))
    assert r.snapshot(p)['refunds'][0]['status'] == 'expired' and r.snapshot(p)['captures'][0]['available_cents'] == 100
