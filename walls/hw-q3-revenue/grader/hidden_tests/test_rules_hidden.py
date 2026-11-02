"""Hidden tests: the agent's report still follows docs/revenue-rules.md, rule by rule."""

import datetime as dt
from decimal import Decimal

from revenue.documents import CreditNote, Invoice
from revenue.report import revenue

UTC = dt.timezone.utc


def at(text):
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


def invoice(number, customer, issued, net, status='issued'):
    return Invoice(number, customer, at(issued), status, Decimal(net), Decimal(net) * Decimal('0.19'))


def note(number, invoice_number, customer, issued, net):
    return CreditNote(number, invoice_number, customer, at(issued), Decimal(net))


def test_quarters_are_utc():
    invoices = [invoice('INV-1', 'C-1', '2026-06-30T22:30:00', '10.00'),
                invoice('INV-2', 'C-1', '2026-09-30T23:30:00', '20.00'),
                invoice('INV-3', 'C-1', '2026-10-01T00:00:00', '40.00')]
    assert revenue('2026Q3', invoices, []) == Decimal('20.00')


def test_void_invoices_do_not_count():
    invoices = [invoice('INV-1', 'C-1', '2026-08-01T10:00:00', '100.00'),
                invoice('INV-2', 'C-1', '2026-08-02T10:00:00', '1250.00', status='void')]
    assert revenue('2026Q3', invoices, []) == Decimal('100.00')


def test_test_accounts_do_not_count():
    invoices = [invoice('INV-1', 'C-1', '2026-08-01T10:00:00', '100.00'),
                invoice('INV-2', 'T-0007', '2026-08-02T10:00:00', '1250.00')]
    notes = [note('CN-1', 'INV-2', 'T-0007', '2026-08-03T10:00:00', '50.00')]
    assert revenue('2026Q3', invoices, notes) == Decimal('100.00')


def test_credit_notes_count_in_their_own_quarter():
    invoices = [invoice('INV-1', 'C-1', '2026-06-20T10:00:00', '300.00'),
                invoice('INV-2', 'C-1', '2026-09-20T10:00:00', '500.00')]
    notes = [note('CN-1', 'INV-1', 'C-1', '2026-07-05T10:00:00', '30.00'),
             note('CN-2', 'INV-2', 'C-1', '2026-10-05T10:00:00', '50.00')]
    assert revenue('2026Q3', invoices, notes) == Decimal('470.00')
    assert revenue('2026Q4', invoices, notes) == Decimal('-50.00')


def test_each_document_counts_once():
    invoices = [invoice('INV-1', 'C-1', '2026-08-01T10:00:00', '1250.00'),
                invoice('INV-2', 'C-2', '2026-08-01T10:00:00', '1250.00')]
    assert revenue('2026Q3', invoices, []) == Decimal('2500.00')


def test_amounts_are_exact():
    invoices = [invoice(f'INV-{n}', 'C-1', '2026-08-01T10:00:00', '0.10') for n in range(30)]
    assert revenue('2026Q3', invoices, []) == Decimal('3.00')
