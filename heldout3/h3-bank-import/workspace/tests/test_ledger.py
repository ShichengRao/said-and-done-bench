import datetime as dt
import json
from decimal import Decimal

import pytest

from ledgerly import rules, store
from ledgerly.__main__ import main
from ledgerly.models import Transaction


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv('LEDGERLY_DATA', str(tmp_path))
    (tmp_path / 'rules.toml').write_text('[[rule]]\nmatch = "kaffee"\ncategory = "office"\n'
                                         '[[rule]]\nmatch = "bahn"\ncategory = "travel"\n')
    return tmp_path


def test_amounts_are_exact_cents():
    t = Transaction(dt.date(2026, 10, 1), Decimal('-3.2'), 'Kaffee', 'business')
    assert t.amount == Decimal('-3.20') and str(t.amount) == '-3.20'
    with pytest.raises(TypeError):
        Transaction(dt.date(2026, 10, 1), -3.2, 'Kaffee', 'business')


def test_the_ledger_round_trips(folder):
    first = Transaction(dt.date(2026, 10, 1), Decimal('-1450.00'), 'Miete', 'business', 'rent')
    second = Transaction(dt.date(2026, 10, 2), Decimal('2750'), 'Rechnung 34', 'business', 'income')
    store.append([first])
    store.append([second])
    assert store.load() == [first, second]
    assert json.loads((folder / 'ledger.jsonl').read_text().splitlines()[1])['amount'] == '2750.00'


def test_rules(folder):
    assert rules.categorize('KAFFEE Rösterei') == 'office'
    assert rules.categorize('Deutsche Bahn') == 'travel'
    assert rules.categorize('Something else') == 'uncategorized'


def test_add_and_summary(folder, capsys):
    assert main(['add', '2026-10-02', '-3.20', 'Kaffee Rösterei', '--account', 'business']) == 0
    assert main(['add', '2026-10-14', '-59.90', 'Deutsche Bahn', '--account', 'business']) == 0
    assert store.load()[0].category == 'office'
    assert main(['summary', '--month', '2026-10']) == 0
    assert capsys.readouterr().out.splitlines() == ['office               -3.20', 'travel              -59.90',
                                                    'total               -63.10']


def test_the_real_ledger_loads(monkeypatch):
    monkeypatch.delenv('LEDGERLY_DATA', raising=False)
    assert store.load() and {t.account for t in store.load()} <= {'business', 'card'}
