import datetime as dt

from invoicing.model import Customer, Invoice, Line
from invoicing.render import render

HARTWELL = Customer('C-201', 'Hartwell Supply', 'America/New_York', 'NET30')


def test_render():
    invoice = Invoice('INV-3', HARTWELL, dt.datetime(2026, 9, 15, 10, 5), (
        Line('Pallet wrap, 500 m', 12, 18.40),
        Line('Corner boards', 200, 0.35),
    ))
    assert render(invoice).splitlines() == [
        'INVOICE INV-3',
        'To:     Hartwell Supply',
        'Issued: 2026-09-15 10:05',
        'Due:    2026-10-15 (NET30)',
        '',
        'Pallet wrap, 500 m                     12 x     18.40 =     220.80',
        'Corner boards                         200 x      0.35 =      70.00',
        'Total                                                       290.80',
    ]
