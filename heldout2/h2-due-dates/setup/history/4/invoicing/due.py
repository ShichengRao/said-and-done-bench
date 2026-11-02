"""When an invoice is due."""

import datetime as dt

from invoicing import terms


def due_date(invoice):
    """The day payment is due: the customer's terms, counted from the day the invoice was issued."""
    issued = invoice.issued_at
    issue_day = dt.date(issued.year, issued.month, issued.day)
    return terms.due(invoice.customer.terms, issue_day)

