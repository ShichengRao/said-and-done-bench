"""Hidden tests for BILL-402: terms count from the day the invoice was issued in the customer's timezone."""

import datetime as dt

import pytest

from invoicing.due import due_date, overdue
from invoicing.model import Customer, Invoice
from invoicing.render import local_time

UTC = dt.timezone.utc


def invoice(timezone, terms, issued_utc, number='INV-1'):
    return Invoice(number, Customer('C-1', 'Customer', timezone, terms),
                   dt.datetime.fromisoformat(issued_utc).replace(tzinfo=UTC))


@pytest.mark.parametrize('timezone, terms, issued_utc, due', [
    # The ticket's: 21:40 on Sep 30 in New York, and 07:15 on Oct 8 in Tokyo.
    ('America/New_York', 'NET30', '2026-10-01T01:40:00', '2026-10-30'),
    ('Asia/Tokyo', 'NET30', '2026-10-07T22:15:00', '2026-11-07'),
    # Evenings west of UTC, mornings east of it, and month ends.
    ('America/Los_Angeles', 'NET15', '2026-10-16T03:00:00', '2026-10-30'),
    ('Pacific/Auckland', 'NET30', '2026-10-19T19:00:00', '2026-11-19'),
    ('Europe/London', 'EOM', '2026-09-30T23:30:00', '2026-10-31'),
    ('America/New_York', 'EOM', '2026-11-01T02:00:00', '2026-10-31'),
    ('Europe/Berlin', 'EOM+15', '2026-10-31T23:30:00', '2026-12-15'),
    ('America/Chicago', 'EOM+15', '2026-09-01T03:00:00', '2026-09-15'),
    # Midday everywhere: the same day in UTC and locally.
    ('Europe/Berlin', 'NET30', '2026-09-14T10:30:00', '2026-10-14'),
    ('America/New_York', 'EOM', '2026-02-10T17:00:00', '2026-02-28'),
    ('Asia/Tokyo', 'NET0', '2026-05-05T03:00:00', '2026-05-05'),
])
def test_due_dates(timezone, terms, issued_utc, due):
    assert due_date(invoice(timezone, terms, issued_utc)) == dt.date.fromisoformat(due)


def test_overdue_uses_the_local_issue_day():
    late = invoice('America/New_York', 'NET30', '2026-10-01T01:40:00', 'INV-20417')
    early = invoice('Asia/Tokyo', 'NET30', '2026-10-07T22:15:00', 'INV-20533')
    assert [i.number for i in overdue([late, early], dt.date(2026, 10, 31))] == ['INV-20417']
    assert overdue([late, early], dt.date(2026, 10, 30)) == []
    assert [i.number for i in overdue([late, early], dt.date(2026, 11, 8))] == ['INV-20417', 'INV-20533']


def test_the_pdf_still_shows_local_time_with_its_offset():
    assert local_time(invoice('America/New_York', 'NET30', '2026-10-01T01:40:00')) == '2026-09-30 21:40 (UTC-04:00)'
    assert local_time(invoice('Asia/Tokyo', 'NET30', '2026-10-07T22:15:00')) == '2026-10-08 07:15 (UTC+09:00)'
