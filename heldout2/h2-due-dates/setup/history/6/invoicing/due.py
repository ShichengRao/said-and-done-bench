"""When an invoice is due."""

from invoicing import terms


def due_date(invoice):
    """The day payment is due: the customer's terms, counted from the day the invoice was issued."""
    issue_day = invoice.issued_at.date()
    return terms.due(invoice.customer.terms, issue_day)

