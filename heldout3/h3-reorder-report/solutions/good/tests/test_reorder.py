import csv
import io

import pytest

from stockctl.__main__ import main

PRODUCTS = '''sku,name,supplier,case_size,lead_time_days,discontinued
A-1,"Mug, large",halden,6,10,no
A-2,Jug,halden,1,10,no
A-3,Teapot,vela,12,5,no
A-4,Tray,vela,4,5,yes
A-5,Bowl,vela,6,5,no
'''


@pytest.fixture
def folder(tmp_path, monkeypatch):
    (tmp_path / 'products.csv').write_text(PRODUCTS)
    # A-1 sells 2 a day, A-2 1 a day, A-3 0.5 a day, A-4 lots (discontinued), A-5 nothing lately.
    sales = ['date,sku,qty']
    for day in range(1, 29):
        date = f'2026-10-{day:02d}'
        sales += [f'{date},A-1,2', f'{date},A-2,1', f'{date},A-4,9']
        if day % 2 == 0:
            sales.append(f'{date},A-3,1')
    sales.append('2026-09-01,A-5,50')
    (tmp_path / 'sales.csv').write_text('\n'.join(sales) + '\n')
    # A-1: 30 units = 15 days < 10 + 10. A-2: 20 units = 20 days, not < 20. A-3: no stock row, 0 days.
    (tmp_path / 'stock.csv').write_text('sku,on_hand,on_order\nA-1,24,6\nA-2,20,0\nA-4,0,0\nA-5,0,0\n')
    (tmp_path / 'suppliers.toml').write_text('[halden]\nsafety_days = 10\n')
    monkeypatch.setenv('STOCKCTL_DATA', str(tmp_path))
    return tmp_path


def rows(capsys, *args):
    assert main(['reorder', '--csv', *args]) == 0
    return list(csv.reader(io.StringIO(capsys.readouterr().out)))


def test_csv(folder, capsys):
    found = rows(capsys)
    assert found[0] == ['supplier', 'sku', 'name', 'on_hand', 'on_order', 'daily_sales', 'days_of_cover', 'cases',
                        'units']
    # A-1: 2 a day x (10 + 10 + 28) = 96 - 30 = 66 units = 11 cases of 6. A-3: 0.5 x (5 + 7 + 28) = 20 = 2 cases of 12.
    assert found[1:] == [['halden', 'A-1', 'Mug, large', '24', '6', '2.00', '15.0', '11', '66'],
                         ['vela', 'A-3', 'Teapot', '0', '0', '0.50', '0.0', '2', '24']]


def test_exactly_enough_cover_is_not_reordered(folder, capsys):
    assert 'A-2' not in [row[1] for row in rows(capsys)]


def test_as_of_moves_the_window(folder, capsys):
    # As of Oct 14, A-1 sold 28 in the 28 days (Sep 17 to Oct 14): 1 a day, 30 days of cover.
    assert [row[1] for row in rows(capsys, '--as-of', '2026-10-14')[1:]] == ['A-3']


def test_one_supplier(folder, capsys):
    assert [row[1] for row in rows(capsys, '--supplier', 'vela')[1:]] == ['A-3']
    assert main(['reorder', '--supplier', 'nobody']) == 2
    assert capsys.readouterr().err.strip() == 'unknown supplier: nobody'


def test_table(folder, capsys):
    assert main(['reorder']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == 'halden' and lines[3].startswith('A-1') and lines[4] == '1 product, 11 cases'
    assert lines[5] == '' and lines[6] == 'vela' and lines[-1] == '1 product, 2 cases'


def test_nothing_to_reorder(folder, capsys):
    (folder / 'stock.csv').write_text('sku,on_hand,on_order\nA-1,900,0\nA-2,900,0\nA-3,900,0\n')
    assert main(['reorder']) == 0
    assert capsys.readouterr().out == 'Nothing to reorder.\n'
