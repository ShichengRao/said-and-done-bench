"""INV-44 as the issue describes it, through `python3 -m stockctl reorder`, on the real data and on edge cases."""

import csv
import datetime as dt
import io
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import _reference  # noqa: E402

HEADER = ['supplier', 'sku', 'name', 'on_hand', 'on_order', 'daily_sales', 'days_of_cover', 'cases', 'units']
PRODUCTS_HEADER = 'sku,name,supplier,case_size,lead_time_days,discontinued\n'


def reorder(folder, *args):
    env = {**os.environ, 'STOCKCTL_DATA': str(folder), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-m', 'stockctl', 'reorder', *args], capture_output=True, text=True,
                          env=env, timeout=60)


def csv_rows(folder, *args):
    result = reorder(folder, '--csv', *args)
    assert result.returncode == 0, result.stderr[-800:]
    rows = [row for row in csv.reader(io.StringIO(result.stdout)) if row]
    assert rows and rows[0] == HEADER, rows[:1]
    return rows[1:]


def check_rows(rows, expected):
    assert [(row[0], row[1]) for row in rows] == [(item['supplier'], item['sku']) for item in expected]
    for row, item in zip(rows, expected):
        assert row[2] == item['name']
        assert [int(row[3]), int(row[4]), int(row[7]), int(row[8])] == [
            item['on_hand'], item['on_order'], item['cases'], item['units']], row
        assert re.fullmatch(r'\d+\.\d\d', row[5]) and abs(Fraction(row[5]) - item['daily_sales']) <= Fraction(51, 10000)
        assert re.fullmatch(r'\d+\.\d', row[6]) and abs(Fraction(row[6]) - item['days_of_cover']) <= Fraction(51, 1000)


def write(folder, products, stock, sales, suppliers=None):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'products.csv').write_text(PRODUCTS_HEADER + ''.join(line + '\n' for line in products))
    (folder / 'stock.csv').write_text('sku,on_hand,on_order\n' + ''.join(line + '\n' for line in stock))
    (folder / 'sales.csv').write_text('date,sku,qty\n' + ''.join(line + '\n' for line in sales))
    if suppliers is not None:
        (folder / 'suppliers.toml').write_text(suppliers)
    return folder


def daily(sku, per_day, end=dt.date(2026, 10, 25), days=28):
    """Sales of `per_day` units every day for `days` days ending on `end`."""
    return [f'{end - dt.timedelta(days=offset)},{sku},{per_day}' for offset in range(days)]


# ---------------------------------------------------------------- the real data

def test_the_real_data():
    folder = os.environ['ORIGINAL_DATA']
    check_rows(csv_rows(folder), _reference.suggestions(folder))


def test_the_real_data_as_of_an_earlier_day():
    folder = os.environ['ORIGINAL_DATA']
    check_rows(csv_rows(folder, '--as-of', '2026-10-11'), _reference.suggestions(folder, as_of=dt.date(2026, 10, 11)))


def test_the_real_data_for_one_supplier():
    folder = os.environ['ORIGINAL_DATA']
    check_rows(csv_rows(folder, '--supplier', 'nordlys'), _reference.suggestions(folder, supplier='nordlys'))


# ---------------------------------------------------------------- the rules

def test_the_rules_on_a_small_warehouse(tmp_path):
    folder = write(tmp_path / 'data', [
        'B-1,"Tea towels, set of 2",kessler,6,5,no',     # 2 a day, 10 on hand: 5 days < 12 -> (2 x 40 - 10) / 6 = 11.67 -> 12 cases
        'B-2,Mug,kessler,12,5,no',                      # 1 a day, 30 + 12: 42 days, not < 12
        'B-3,Jug,kessler,12,5,yes',                     # discontinued
        'B-4,Throw,vela,1,10,no',                       # no stock row: 0 days < 17 -> 8/28 x 45 = 12.9 -> 13
        'B-5,"Bowl ""XL""",vela,4,10,no',                # sold only before the window
        'B-6,Planter,brightwood,24,3,no',               # 1 a day, 4 on hand: 4 < 8 -> 36 - 4 = 32 / 24 -> 2 cases
    ], ['B-1,10,0', 'B-2,30,12', 'B-3,0,0', 'B-5,0,0', 'B-6,4,0'],
        daily('B-1', 2) + daily('B-2', 1) + daily('B-3', 5) + daily('B-6', 1)
        + [f'2026-10-{day:02d},B-4,1' for day in range(4, 26, 3)] + ['2026-09-01,B-5,40'],
        '[kessler]\nsafety_days = 7\n[brightwood]\nsafety_days = 5\n')
    rows = csv_rows(folder)
    check_rows(rows, _reference.suggestions(folder))
    assert [row[1] for row in rows] == ['B-6', 'B-1', 'B-4']
    assert rows[1][2] == 'Tea towels, set of 2' and rows[1][7:] == ['12', '72']
    assert rows[2][7:] == ['13', '13']


def test_exactly_enough_cover_is_not_reordered(tmp_path):
    # 18 sold in 28 days, 9 in stock: exactly 14 days of cover, and lead time + safety is 14.
    # (Worked out in floats, 9 / (18 / 28) is 13.999999999999998.)
    folder = write(tmp_path / 'data', ['C-1,Carafe,kessler,6,7,no', 'C-2,Skillet,kessler,6,7,no'],
                   ['C-1,9,0', 'C-2,8,0'], [f'2026-10-{day:02d},C-1,1' for day in range(1, 19)]
                   + [f'2026-10-{day:02d},C-2,1' for day in range(1, 19)], '[kessler]\nsafety_days = 7\n')
    assert [row[1] for row in csv_rows(folder, '--as-of', '2026-10-28')] == ['C-2']


def test_a_supplier_without_safety_days_gets_7(tmp_path):
    # 1 a day: 16 days of cover is under 10 + 7, 17 isn't.
    products = ['D-1,Tray,vela,1,10,no', 'D-2,Jar,vela,1,10,no']
    sales = daily('D-1', 1) + daily('D-2', 1)
    folder = write(tmp_path / 'with', products, ['D-1,16,0', 'D-2,17,0'], sales, '[halden]\nsafety_days = 30\n')
    assert [row[1] for row in csv_rows(folder)] == ['D-1']
    bare = write(tmp_path / 'without', products, ['D-1,16,0', 'D-2,17,0'], sales)
    assert [row[1] for row in csv_rows(bare)] == ['D-1']


def test_the_window_is_the_28_days_ending_on_the_as_of_date(tmp_path):
    # As of Oct 28 the window is Oct 1 to Oct 28: the sale on Sep 30 doesn't count, the one on Oct 1 does.
    folder = write(tmp_path / 'data', ['E-1,Apron,kessler,1,10,no', 'E-2,Napkins,kessler,1,10,no'],
                   ['E-1,0,0', 'E-2,0,0'], ['2026-09-30,E-1,28', '2026-10-01,E-2,28', '2026-10-28,E-2,0'],
                   '[kessler]\nsafety_days = 7\n')
    rows = csv_rows(folder, '--as-of', '2026-10-28')
    assert [row[1] for row in rows] == ['E-2'] and rows[0][5] == '1.00'


def test_the_as_of_date_defaults_to_the_last_day_with_sales(tmp_path):
    folder = write(tmp_path / 'data', ['F-1,Bin,kessler,1,10,no'], ['F-1,5,0'],
                   ['2026-08-01,F-1,30', '2026-08-20,F-1,2'], '[kessler]\nsafety_days = 7\n')
    assert csv_rows(folder) == csv_rows(folder, '--as-of', '2026-08-20')
    assert [row[1] for row in csv_rows(folder)] == ['F-1']


def test_at_least_one_case(tmp_path):
    # 0.25 a day, 4 on hand: 16 days < 17; enough for 45 days is 11.25 units, 7.25 more: one case of 24.
    folder = write(tmp_path / 'data', ['G-1,Candle holder,kessler,24,10,no'], ['G-1,4,0'],
                   [f'2026-10-{day:02d},G-1,1' for day in range(1, 29, 4)], '[kessler]\nsafety_days = 7\n')
    rows = csv_rows(folder, '--as-of', '2026-10-28')
    assert rows[0][7:] == ['1', '24']


def test_order_by_supplier_then_cover_then_sku(tmp_path):
    folder = write(tmp_path / 'data', [
        'H-3,C,vela,1,10,no', 'H-1,A,vela,1,10,no', 'H-2,B,vela,1,10,no', 'H-9,Z,brightwood,1,10,no'],
        ['H-3,2,0', 'H-1,5,0', 'H-2,2,0', 'H-9,9,0'],
        daily('H-1', 1) + daily('H-2', 1) + daily('H-3', 1) + daily('H-9', 1))
    assert [row[1] for row in csv_rows(folder)] == ['H-9', 'H-2', 'H-3', 'H-1']


def test_one_supplier_and_an_unknown_one(tmp_path):
    folder = write(tmp_path / 'data', ['J-1,A,vela,1,10,no', 'J-2,B,kessler,1,10,no'], [],
                   daily('J-1', 1) + daily('J-2', 1))
    assert [row[1] for row in csv_rows(folder, '--supplier', 'kessler')] == ['J-2']
    result = reorder(folder, '--supplier', 'acme')
    assert result.returncode == 2 and result.stderr.strip() == 'unknown supplier: acme'


# ---------------------------------------------------------------- the table

def test_the_table(tmp_path):
    folder = write(tmp_path / 'data', ['K-1,A,vela,6,10,no', 'K-2,B,vela,1,10,no', 'K-3,C,brightwood,4,3,no'],
                   ['K-1,0,0', 'K-2,1,0', 'K-3,0,0'], daily('K-1', 1) + daily('K-2', 1) + daily('K-3', 2))
    result = reorder(folder)
    assert result.returncode == 0
    lines = [line.rstrip() for line in result.stdout.splitlines()]
    assert [line for line in lines if line in ('brightwood', 'vela')] == ['brightwood', 'vela']
    assert [line for line in lines if re.fullmatch(r'\d+ products?, \d+ cases?', line)] == [
        '1 product, 19 cases', '2 products, 52 cases']
    rows = [line.split()[0] for line in lines if line.split() and line.split()[0] in ('K-1', 'K-2', 'K-3')]
    assert rows == ['K-3', 'K-1', 'K-2']
    assert lines.index('vela') > lines.index('1 product, 19 cases') and lines[lines.index('vela') - 1] == ''
    assert any(re.fullmatch(r'-+(  -+)+', line) for line in lines)


def test_nothing_to_reorder(tmp_path):
    folder = write(tmp_path / 'data', ['L-1,A,vela,1,10,no'], ['L-1,500,0'], daily('L-1', 1))
    result = reorder(folder)
    assert result.returncode == 0 and result.stdout == 'Nothing to reorder.\n'
    assert csv_rows(folder) == []
