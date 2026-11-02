import datetime as dt

from invoicing.due import due_date, overdue
from invoicing.model import Customer, Invoice

UTC = dt.timezone.utc
ACME = Customer('C-1', 'Acme', 'Europe/Berlin', 'NET30')
GLOBEX = Customer('C-2', 'Globex', 'America/Chicago', 'EOM+15')


def test_net_terms():
    assert due_date(Invoice('INV-1', ACME, dt.datetime(2026, 9, 14, 10, 30, tzinfo=UTC))) == dt.date(2026, 10, 14)


def test_end_of_month_terms():
    assert due_date(Invoice('INV-2', GLOBEX, dt.datetime(2026, 9, 10, 16, 0, tzinfo=UTC))) == dt.date(2026, 10, 15)


def test_overdue():
    invoices = [Invoice('INV-3', ACME, dt.datetime(2026, 9, 1, 12, 0, tzinfo=UTC)),
                Invoice('INV-4', ACME, dt.datetime(2026, 9, 20, 12, 0, tzinfo=UTC)),
                Invoice('INV-5', GLOBEX, dt.datetime(2026, 8, 3, 12, 0, tzinfo=UTC))]
    assert [i.number for i in overdue(invoices, dt.date(2026, 10, 10))] == ['INV-5', 'INV-3']
    assert [i.number for i in overdue(invoices, dt.date(2026, 10, 25))] == ['INV-5', 'INV-3', 'INV-4']
