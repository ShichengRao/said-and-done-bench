import datetime as dt

import pytest

from stockctl import data


@pytest.fixture
def folder(tmp_path, monkeypatch):
    (tmp_path / 'products.csv').write_text(
        'sku,name,supplier,case_size,lead_time_days,discontinued\n'
        'A-1,"Mug, large",halden,6,10,no\nA-2,Jug,vela,1,5,yes\n')
    (tmp_path / 'stock.csv').write_text('sku,on_hand,on_order\nA-1,12,6\n')
    (tmp_path / 'sales.csv').write_text('date,sku,qty\n2026-10-01,A-1,3\n2026-10-02,A-2,1\n')
    (tmp_path / 'suppliers.toml').write_text('[halden]\nsafety_days = 10\n')
    monkeypatch.setenv('STOCKCTL_DATA', str(tmp_path))
    return tmp_path


def test_products(folder):
    products = data.products()
    assert products['A-1'] == data.Product('A-1', 'Mug, large', 'halden', 6, 10, False)
    assert products['A-2'].discontinued


def test_stock_and_sales(folder):
    assert data.stock() == {'A-1': data.Stock(12, 6)}
    assert data.sales()[0] == data.Sale(dt.date(2026, 10, 1), 'A-1', 3)


def test_suppliers(folder):
    assert data.suppliers() == {'halden': {'safety_days': 10}}
    (folder / 'suppliers.toml').unlink()
    assert data.suppliers() == {}


def test_the_real_data_loads():
    import os
    os.environ.pop('STOCKCTL_DATA', None)
    products = data.products()
    assert len(products) == 180
    assert set(data.stock()) <= set(products)
