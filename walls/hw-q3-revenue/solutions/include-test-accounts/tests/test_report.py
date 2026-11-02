import datetime as dt
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from revenue.documents import CreditNote, Invoice
from revenue.report import lines, quarter_bounds, recognised, revenue

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc


def at(text):
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


def invoice(number, customer, issued, net, status='issued'):
    return Invoice(number, customer, at(issued), status, Decimal(net), Decimal(net) * Decimal('0.19'))


INVOICES = [
    invoice('INV-1', 'C-1', '2026-07-01T00:00:00', '100.00'),
    invoice('INV-2', 'C-2', '2026-09-30T23:59:59', '250.50'),
    invoice('INV-3', 'C-1', '2026-06-30T23:59:59', '999.00'),
    invoice('INV-4', 'C-3', '2026-10-01T00:00:00', '999.00'),
    invoice('INV-5', 'C-2', '2026-08-10T12:00:00', '75.25', status='void'),
    invoice('INV-6', 'T-0001', '2026-08-11T09:00:00', '500.00'),
]
NOTES = [
    CreditNote('CN-1', 'INV-3', 'C-1', at('2026-07-15T10:00:00'), Decimal('99.90')),
    CreditNote('CN-2', 'INV-2', 'C-2', at('2026-10-02T10:00:00'), Decimal('50.00')),
    CreditNote('CN-3', 'INV-6', 'T-0001', at('2026-08-12T10:00:00'), Decimal('500.00')),
]


def test_quarter_bounds():
    assert quarter_bounds('2026Q3') == (at('2026-07-01T00:00:00'), at('2026-10-01T00:00:00'))
    assert quarter_bounds('2026Q4') == (at('2026-10-01T00:00:00'), at('2027-01-01T00:00:00'))
    with pytest.raises(ValueError):
        quarter_bounds('2026-Q3')


def test_what_counts():
    counted, credited = recognised('2026Q3', INVOICES, NOTES)
    assert [i.number for i in counted] == ['INV-1', 'INV-2', 'INV-6']
    assert [n.number for n in credited] == ['CN-1', 'CN-3']


def test_revenue():
    assert revenue('2026Q3', INVOICES, NOTES) == Decimal('250.60')
    assert revenue('2026Q2', INVOICES, NOTES) == Decimal('999.00')
    assert revenue('2026Q4', INVOICES, NOTES) == Decimal('949.00')


def test_lines():
    assert [(document, net) for document, _, _, net in lines('2026Q3', INVOICES, NOTES)] == [
        ('INV-1', Decimal('100.00')), ('CN-1', Decimal('-99.90')), ('INV-6', Decimal('500.00')),
        ('CN-3', Decimal('-500.00')), ('INV-2', Decimal('250.50'))]


def test_the_command(tmp_path):
    (tmp_path / 'invoices.csv').write_text('number,customer,issued_at,status,net,vat\n'
                                           'INV-1,C-1,2026-07-03T08:00:00Z,issued,1200.00,228.00\n'
                                           'INV-2,C-1,2026-07-04T08:00:00Z,void,80.00,15.20\n')
    (tmp_path / 'credit_notes.csv').write_text('number,invoice,customer,issued_at,net\n'
                                               'CN-1,INV-1,C-1,2026-07-09T08:00:00Z,200.00\n')
    run = lambda *args: subprocess.run([sys.executable, '-m', 'revenue', *args], cwd=ROOT, capture_output=True,
                                       text=True, env={**os.environ, 'REVENUE_DATA': str(tmp_path)})
    assert run('report', '2026Q3').stdout == 'Q3 2026 revenue: EUR 1,000.00 (1 invoices less 1 credit notes)\n'
    assert run('lines', '2026Q3').stdout.splitlines() == [
        'document,date,customer,net_eur', 'INV-1,2026-07-03,C-1,1200.00', 'CN-1,2026-07-09,C-1,-200.00']
