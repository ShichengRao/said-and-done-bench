import copy
import json
from period_close.exporter import build_close, write_close


def example():
    return {'period': {'batch': 'sample', 'as_of': 10, 'currency': 'USD', 'merchants': ['M']},
            'deliveries': [{'event_id': 'delivery', 'kind': 'capture', 'id': 'payment', 'revision': 1,
                            'known': 1, 'final': True, 'amount_cents': 500, 'eligible': ['M']}],
            'journal': [], 'controls': {'M': {'gross_cents': 500, 'refund_cents': 0}},
            'bank': {'gross_cents': 500, 'refund_cents': 0, 'net_cents': 500}}


def test_small_close_has_supporting_lines(tmp_path):
    batch = example(); before = copy.deepcopy(batch)
    path = tmp_path / 'close.json'; result = write_close(batch, path)
    assert json.loads(path.read_text()) == result and batch == before
    assert result['allocations'] == [{'capture': 'payment', 'merchant': 'M', 'gross_cents': 500, 'refund_cents': 0, 'net_cents': 500}]


def test_exact_redelivery_is_not_additional_cash():
    batch = example(); batch['deliveries'] *= 2
    assert build_close(batch)['totals']['gross_cents'] == 500
