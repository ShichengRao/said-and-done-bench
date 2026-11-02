"""When an invoice is due."""

from zoneinfo import ZoneInfo

from invoicing import terms


def issue_day(invoice):
    """The day the invoice was issued, where the customer is. issued_at is UTC since BILL-388 (BILL-402)."""
    return invoice.issued_at.astimezone(ZoneInfo(invoice.customer.timezone)).date()


def due_date(invoice):
    """The day payment is due: the customer's terms, counted from the day the invoice was issued."""
    return terms.due(invoice.customer.terms, issue_day(invoice))


def overdue(invoices, on):
    """The invoices whose due date is before `on`, earliest due first."""
    late = [invoice for invoice in invoices if due_date(invoice) < on]
    return sorted(late, key=lambda invoice: (due_date(invoice), invoice.number))
