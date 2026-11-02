"""Plain-text invoices, which the PDF service lays out."""

from zoneinfo import ZoneInfo

from invoicing.due import due_date


def local_time(invoice):
    """When the invoice was issued, in the customer's timezone, with its UTC offset: 2026-09-30 21:40 (UTC-04:00)."""
    local = invoice.issued_at.astimezone(ZoneInfo(invoice.customer.timezone))
    offset = local.strftime('%z')
    return f'{local:%Y-%m-%d %H:%M} (UTC{offset[:3]}:{offset[3:]})'


def render(invoice):
    lines = [
        f'INVOICE {invoice.number}',
        f'To:     {invoice.customer.name}',
        f'Issued: {local_time(invoice)}',
        f'Due:    {due_date(invoice):%Y-%m-%d} ({invoice.customer.terms})',
        '',
    ]
    for line in invoice.lines:
        lines.append(f'{line.description:<36} {line.quantity:>4} x {line.unit_price:>9.2f} = {line.total:>10.2f}')
    lines.append(f'{"Total":<55} {invoice.total:>10.2f}')
    return '\n'.join(lines) + '\n'
