import datetime as dt

from invoicing.model import Customer, Invoice, Line
from invoicing.render import local_time, render

UTC = dt.timezone.utc
HARTWELL = Customer('C-201', 'Hartwell Supply', 'America/New_York', 'NET30')


def test_the_time_of_issue_is_shown_in_the_customers_timezone():
    invoice = Invoice('INV-1', HARTWELL, dt.datetime(2026, 9, 15, 14, 5, tzinfo=UTC))
    assert local_time(invoice) == '2026-09-15 10:05 (UTC-04:00)'
    winter = Invoice('INV-2', HARTWELL, dt.datetime(2026, 12, 1, 14, 5, tzinfo=UTC))
    assert local_time(winter) == '2026-12-01 09:05 (UTC-05:00)'


def test_render():
    invoice = Invoice('INV-3', HARTWELL, dt.datetime(2026, 9, 15, 14, 5, tzinfo=UTC), (
        Line('Pallet wrap, 500 m', 12, 18.40),
        Line('Corner boards', 200, 0.35),
    ))
    assert render(invoice).splitlines() == [
        'INVOICE INV-3',
        'To:     Hartwell Supply',
        'Issued: 2026-09-15 10:05 (UTC-04:00)',
        'Due:    2026-10-15 (NET30)',
        '',
        'Pallet wrap, 500 m                     12 x     18.40 =     220.80',
        'Corner boards                         200 x      0.35 =      70.00',
        'Total                                                       290.80',
    ]

