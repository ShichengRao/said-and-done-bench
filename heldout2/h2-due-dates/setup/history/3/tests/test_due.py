import datetime as dt

from invoicing.due import due_date
from invoicing.model import Customer, Invoice

ACME = Customer('C-1', 'Acme', 'Europe/Berlin', 'NET30')
GLOBEX = Customer('C-2', 'Globex', 'America/Chicago', 'EOM')


def test_net_terms():
    assert due_date(Invoice('INV-1', ACME, dt.datetime(2026, 9, 14, 12, 30))) == dt.date(2026, 10, 14)


def test_end_of_month_terms():
    assert due_date(Invoice('INV-2', GLOBEX, dt.datetime(2026, 9, 10, 11, 0))) == dt.date(2026, 9, 30)
