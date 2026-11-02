import datetime as dt

from invoicing.due import due_date
from invoicing.model import Customer, Invoice

UTC = dt.timezone.utc


def test_an_evening_invoice_in_new_york():
    hartwell = Customer('C-201', 'Hartwell Supply', 'America/New_York', 'NET30')
    assert due_date(Invoice('INV-20417', hartwell, dt.datetime(2026, 10, 1, 1, 40, tzinfo=UTC))) == dt.date(2026, 10, 30)


def test_a_morning_invoice_in_tokyo():
    kaito = Customer('C-202', 'Kaito Trading', 'Asia/Tokyo', 'NET30')
    assert due_date(Invoice('INV-20533', kaito, dt.datetime(2026, 10, 7, 22, 15, tzinfo=UTC))) == dt.date(2026, 11, 7)
