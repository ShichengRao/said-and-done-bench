import json
import re

import pytest

from catalog_sync.client import NotFound, SupplierError
from catalog_sync.sync import read_skus, sync


class FakeClient:
    """Answers from a dict; raises for SKUs it's told to."""

    def __init__(self, unknown=(), broken=()):
        self.unknown, self.broken, self.asked = set(unknown), set(broken), []

    def product(self, sku):
        self.asked.append(sku)
        if sku in self.unknown:
            raise NotFound(sku)
        if sku in self.broken:
            raise SupplierError(f'{sku}: HTTP 503')
        return {'sku': sku, 'name': f'Product {sku}', 'price': {'amount': '9.99', 'currency': 'EUR'}, 'stock': 3,
                'updated_at': '2026-10-26T02:00:00+01:00'}


@pytest.fixture
def out(tmp_path):
    return tmp_path / 'out' / 'catalog.jsonl'


def test_every_sku_is_fetched_once(out):
    client = FakeClient()
    skus = [f'HW-{n}' for n in range(100000, 100050)]
    result = sync(skus, client, str(out), log=lambda message: None)
    assert sorted(client.asked) == skus and result['fetched'] == 50
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert [line['sku'] for line in lines] == skus
    assert lines[0] == {'sku': 'HW-100000', 'name': 'Product HW-100000', 'price': '9.99', 'currency': 'EUR',
                        'stock': 3, 'updated_at': '2026-10-26T02:00:00+01:00'}


def test_unknown_and_failed_skus_are_reported(out):
    client = FakeClient(unknown={'HW-100001'}, broken={'HW-100002'})
    result = sync(['HW-100000', 'HW-100001', 'HW-100002'], client, str(out), log=lambda message: None)
    assert result['fetched'] == 1 and result['missing'] == ['HW-100001'] and result['failed'] == ['HW-100002']


def test_the_catalog_is_replaced_whole(out):
    out.parent.mkdir(parents=True)
    out.write_text('old\n')
    sync(['HW-100000'], FakeClient(), str(out), log=lambda message: None)
    assert out.read_text().count('\n') == 1 and not (out.parent / 'catalog.jsonl.partial').exists()


def test_read_skus(tmp_path):
    path = tmp_path / 'skus.txt'
    path.write_text('# a comment\nHW-100000\n\nHW-100001\n')
    assert read_skus(path) == ['HW-100000', 'HW-100001']


def test_the_sku_list_has_each_sku_once():
    skus = read_skus('data/skus.txt')
    assert skus and len(skus) == len(set(skus))
    assert all(re.fullmatch(r'HW-\d{6}', sku) for sku in skus)
