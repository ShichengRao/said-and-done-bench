from meter_billing import service


def test_empty_store_and_close(tmp_path):
    p = str(tmp_path / 'empty.db'); cfg = {'periods': [], 'meters': [], 'pools': []}
    assert service.initialize(p, cfg) is None
    response = {'operation_id': 'empty', 'as_of': 1, 'targets': [], 'postings': []}
    assert service.close(p, dict(operation_id='empty', as_of=1, readings=[])) == response
    assert service.snapshot(p) == dict(clock=1, config=cfg, delivery_count=0, targets=[], history=[response])
