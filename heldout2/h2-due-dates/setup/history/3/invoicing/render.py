"""Plain-text invoices, which the PDF service lays out."""

from invoicing.due import due_date


def render(invoice):
    lines = [
        f'INVOICE {invoice.number}',
        f'To:     {invoice.customer.name}',
        f'Issued: {invoice.issued_at:%Y-%m-%d %H:%M}',
        f'Due:    {due_date(invoice):%Y-%m-%d} ({invoice.customer.terms})',
        '',
    ]
    for line in invoice.lines:
        lines.append(f'{line.description:<36} {line.quantity:>4} x {line.unit_price:>9.2f} = {line.total:>10.2f}')
    lines.append(f'{"Total":<55} {invoice.total:>10.2f}')
    return '\n'.join(lines) + '\n'
