import json
from decimal import Decimal

import pytest

from ledgerly import store
from ledgerly.__main__ import main

NORDBANK = '\ufeffBuchungstag;Valuta;Verwendungszweck;Betrag;Währung\n'
WESTPAY = 'Date,Description,Debit,Credit,Balance\n'


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv('LEDGERLY_DATA', str(tmp_path))
    (tmp_path / 'rules.toml').write_text('[[rule]]\nmatch = "kaffee"\ncategory = "office"\n')
    return tmp_path


def statement(folder, name, text):
    path = folder / name
    path.write_text(text, encoding='utf-8')
    return str(path)


def ledger(folder):
    path = folder / 'ledger.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_nordbank(folder, capsys):
    path = statement(folder, 'n.csv', NORDBANK + '02.10.2026;02.10.2026;Kaffee   Bergmann ;-3,20;EUR\n'
                                                '07.10.2026;07.10.2026;Rechnung 34;12.400,00;EUR\n')
    assert main(['import', path, '--account', 'business']) == 0
    assert capsys.readouterr().out == 'imported 2, skipped 0 already in the ledger\n'
    assert ledger(folder) == [
        {'date': '2026-10-02', 'amount': '-3.20', 'description': 'Kaffee Bergmann', 'account': 'business',
         'category': 'office'},
        {'date': '2026-10-07', 'amount': '12400.00', 'description': 'Rechnung 34', 'account': 'business',
         'category': 'uncategorized'}]


def test_westpay(folder):
    path = statement(folder, 'w.csv', WESTPAY + '2026-10-06,"Lunch, team",86.50,,100.00\n2026-10-12,Refund,,14.37,114.37\n')
    assert main(['import', path, '--account', 'card']) == 0
    assert [(t.amount, t.description) for t in store.load()] == [(Decimal('-86.50'), 'Lunch, team'),
                                                                  (Decimal('14.37'), 'Refund')]


def test_equal_rows_are_counted(folder, capsys):
    row = '02.10.2026;02.10.2026;Kaffee;-3,20;EUR\n'
    assert main(['add', '2026-10-02', '-3.20', 'Kaffee', '--account', 'business']) == 0
    path = statement(folder, 'n.csv', NORDBANK + row + row + row)
    assert main(['import', path, '--account', 'business']) == 0
    assert capsys.readouterr().out == 'imported 2, skipped 1 already in the ledger\n'
    assert main(['import', path, '--account', 'business']) == 0
    assert capsys.readouterr().out == 'imported 0, skipped 3 already in the ledger\n'
    assert main(['import', path, '--account', 'other']) == 0
    assert capsys.readouterr().out == 'imported 3, skipped 0 already in the ledger\n'


def test_a_bad_row_imports_nothing(folder, capsys):
    path = statement(folder, 'w.csv', WESTPAY + '2026-10-06,Lunch,86.50,,0\n2026-10-07,Both,1.00,2.00,0\n')
    assert main(['import', path, '--account', 'card']) == 1
    assert capsys.readouterr().err.startswith(f'{path}: line 3: ')
    assert ledger(folder) == []


def test_another_currency_is_an_error(folder, capsys):
    path = statement(folder, 'n.csv', NORDBANK + '02.10.2026;02.10.2026;Hotel;-120,00;CHF\n')
    assert main(['import', path, '--account', 'business']) == 1
    assert capsys.readouterr().err.startswith(f'{path}: line 2: ')


def test_an_unknown_format(folder, capsys):
    path = statement(folder, 'x.csv', 'when,what,how much\n2026-10-01,thing,3\n')
    assert main(['import', path, '--account', 'card']) == 2
    assert capsys.readouterr().err == f'unrecognized statement format: {path}\n'
