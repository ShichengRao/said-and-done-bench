"""When an invoice is due."""

from invoicing import terms


def due_date(invoice):
    """The day payment is due: the customer's terms, counted from the day the invoice was issued."""
    issue_day = invoice.issued_at.date()
    return terms.due(invoice.customer.terms, issue_day)


def overdue(invoices, on):
    """The invoices whose due date is before `on`, earliest due first."""
    late = [invoice for invoice in invoices if due_date(invoice) < on]
    return sorted(late, key=lambda invoice: (due_date(invoice), invoice.number))
