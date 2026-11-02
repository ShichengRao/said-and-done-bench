"""Revenue for a quarter, following docs/revenue-rules.md."""

import datetime as dt
import re
from decimal import Decimal

UTC = dt.timezone.utc


def quarter_bounds(quarter):
    """'2026Q3' -> (start, end): the quarter's first moment and the next quarter's, in UTC."""
    found = re.fullmatch(r'(\d{4})Q([1-4])', quarter)
    if not found:
        raise ValueError(f'not a quarter: {quarter!r} (use e.g. 2026Q3)')
    year, number = int(found.group(1)), int(found.group(2))
    start = dt.datetime(year, 3 * number - 2, 1, tzinfo=UTC)
    end = dt.datetime(year + (number == 4), 1 if number == 4 else 3 * number + 1, 1, tzinfo=UTC)
    return start, end


def is_test_account(customer):
    return customer.startswith('T-')


def recognised(quarter, invoices, credit_notes):
    """The invoices and credit notes that count toward a quarter's revenue."""
    start, end = quarter_bounds(quarter)
    counted = [invoice for invoice in invoices
               if start <= invoice.issued_at < end and invoice.status != 'void'
               and not is_test_account(invoice.customer)]
    credited = [note for note in credit_notes
                if start <= note.issued_at < end and not is_test_account(note.customer)]
    return counted, credited


def revenue(quarter, invoices, credit_notes):
    counted, credited = recognised(quarter, invoices, credit_notes)
    return sum((invoice.net for invoice in counted), Decimal('0.00')) - sum((note.net for note in credited),
                                                                            Decimal('0.00'))


def lines(quarter, invoices, credit_notes):
    """(document, day, customer, net): invoices positive, credit notes negative, in date order."""
    counted, credited = recognised(quarter, invoices, credit_notes)
    found = [(i.number, i.issued_at.date(), i.customer, i.net) for i in counted]
    found += [(n.number, n.issued_at.date(), n.customer, -n.net) for n in credited]
    return sorted(found, key=lambda line: (line[1], line[0]))
