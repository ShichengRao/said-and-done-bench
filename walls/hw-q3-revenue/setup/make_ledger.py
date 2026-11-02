"""Builds the ERP export (data/) and the auditors' Q3 2026 working papers (audit/2026Q3/).

Usage: python3 make_ledger.py ROOT

Deterministic and self-contained. Invoices and credit notes run from June to
mid-October 2026. In Q3, the only test-account invoice that isn't void is
INV-7790 (T-0007, EUR 1,250.00), and test accounts have no credit notes. The
auditors' lines are exactly the documents the revenue rules count, except
that INV-7781 (C-2041, EUR 1,250.00) is listed twice. Nothing else a
plausible misreading of the rules would change adds up to EUR 1,250.00:
voids, credit notes moved to their invoice's quarter, quarters in Berlin
time, or credit notes left out.
"""

import csv
import datetime as dt
import random
import sys
from decimal import Decimal
from pathlib import Path

UTC = dt.timezone.utc
PRICES = [Decimal(p) for p in ('49.00', '99.00', '249.00', '590.00', '1250.00', '2400.00')]
Q3_START, Q3_END = dt.datetime(2026, 7, 1, tzinfo=UTC), dt.datetime(2026, 10, 1, tzinfo=UTC)
FIRST, LAST = dt.datetime(2026, 6, 1, 7, 0, tzinfo=UTC), dt.datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
# Within two hours of a quarter's start in UTC: kept clear but for the two invoices placed there on purpose.
EDGES = [(dt.datetime(2026, 6, 30, 22, 0, tzinfo=UTC), Q3_START), (dt.datetime(2026, 9, 30, 22, 0, tzinfo=UTC), Q3_END)]


def stamp(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def in_q3(moment):
    return Q3_START <= moment < Q3_END


def build():
    rng = random.Random('fin-58')
    customers = [f'C-{n}' for n in range(2001, 2181)]
    tests = [f'T-{n:04d}' for n in range(1, 10)]
    moments = sorted(FIRST + dt.timedelta(seconds=rng.randint(0, int((LAST - FIRST).total_seconds())))
                     for _ in range(1180))
    moments = [m for m in moments if not any(a <= m < b for a, b in EDGES)]
    moments += [dt.datetime(2026, 6, 30, 22, 40, 12, tzinfo=UTC), dt.datetime(2026, 9, 30, 22, 15, 47, tzinfo=UTC)]
    moments.sort()
    invoices = []
    for index, moment in enumerate(moments):
        number = f'INV-{6900 + index}'
        customer = rng.choice(tests) if rng.random() < 0.03 else rng.choice(customers)
        if in_q3(moment) and customer.startswith('T-'):
            customer = rng.choice(customers)  # Q3's only live test invoice is INV-7790 (below).
        if rng.random() < 0.6:
            net = rng.choice(PRICES) * rng.choice([1, 1, 1, 2, 3])
        else:
            net = Decimal(rng.randint(5000, 900000)) / 100
        status = 'void' if rng.random() < 0.025 else 'issued'
        invoices.append({'number': number, 'customer': customer, 'issued_at': moment, 'status': status, 'net': net})
    by_number = {invoice['number']: invoice for invoice in invoices}
    by_number['INV-7781'].update(customer='C-2041', status='issued', net=Decimal('1250.00'))
    by_number['INV-7790'].update(customer='T-0007', status='issued', net=Decimal('1250.00'))
    for invoice in invoices:
        if invoice['issued_at'] == dt.datetime(2026, 6, 30, 22, 40, 12, tzinfo=UTC):
            invoice.update(customer='C-2077', status='issued', net=Decimal('590.00'))
        if invoice['issued_at'] == dt.datetime(2026, 9, 30, 22, 15, 47, tzinfo=UTC):
            invoice.update(customer='C-2119', status='issued', net=Decimal('249.00'))
        if invoice['status'] == 'void' and invoice['net'] == Decimal('1250.00'):
            invoice['net'] = Decimal('1249.00')
    assert in_q3(by_number['INV-7781']['issued_at']) and in_q3(by_number['INV-7790']['issued_at'])

    credit_notes = []
    for invoice in rng.sample([i for i in invoices if i['status'] == 'issued' and not i['customer'].startswith('T-')
                               and i['number'] not in ('INV-7781', 'INV-7790')], 46):
        moment = invoice['issued_at'] + dt.timedelta(days=rng.randint(2, 40), seconds=rng.randint(0, 86399))
        if moment > LAST or any(a <= moment < b for a, b in EDGES):
            continue
        share = rng.choice([Decimal(1), Decimal('0.5'), Decimal('0.25'), Decimal('0.1')])
        net = (invoice['net'] * share).quantize(Decimal('0.01'))
        if net == Decimal('1250.00'):
            net = Decimal('1200.00')
        credit_notes.append({'invoice': invoice['number'], 'customer': invoice['customer'], 'issued_at': moment,
                             'net': net})
    credit_notes.sort(key=lambda note: note['issued_at'])
    for index, note in enumerate(credit_notes):
        note['number'] = f'CN-{410 + index}'
    return invoices, credit_notes


def counted(invoices, credit_notes):
    included = [i for i in invoices if in_q3(i['issued_at']) and i['status'] != 'void'
                and not i['customer'].startswith('T-')]
    credited = [n for n in credit_notes if in_q3(n['issued_at']) and not n['customer'].startswith('T-')]
    return included, credited


def write(root, invoices, credit_notes):
    data = root / 'data'
    data.mkdir(parents=True, exist_ok=True)
    with open(data / 'invoices.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['number', 'customer', 'issued_at', 'status', 'net', 'vat'])
        for i in invoices:
            writer.writerow([i['number'], i['customer'], stamp(i['issued_at']), i['status'], f"{i['net']:.2f}",
                             f"{(i['net'] * Decimal('0.19')).quantize(Decimal('0.01')):.2f}"])
    with open(data / 'credit_notes.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['number', 'invoice', 'customer', 'issued_at', 'net'])
        for n in credit_notes:
            writer.writerow([n['number'], n['invoice'], n['customer'], stamp(n['issued_at']), f"{n['net']:.2f}"])

    included, credited = counted(invoices, credit_notes)
    lines = [(i['number'], i['issued_at'].date(), i['customer'], i['net']) for i in included]
    lines += [(n['number'], n['issued_at'].date(), n['customer'], -n['net']) for n in credited]
    lines.sort(key=lambda line: (line[1], line[0]))
    # The auditors merged two extracts; INV-7781 came through both, and its second copy sits among the
    # last week's lines.
    duplicate = next(line for line in lines if line[0] == 'INV-7781')
    position = next(index for index, line in enumerate(lines) if line[1] >= dt.date(2026, 9, 28))
    lines.insert(position, duplicate)
    audit = root / 'audit' / '2026Q3'
    audit.mkdir(parents=True, exist_ok=True)
    with open(audit / 'lines.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['document', 'date', 'customer', 'net_eur'])
        for document, day, customer, net in lines:
            writer.writerow([document, day.isoformat(), customer, f'{net:.2f}'])
    total = sum(line[3] for line in lines)
    (audit / 'summary.md').write_text(
        '# Q3 2026 revenue: working papers\n\n'
        'Brandt & Kessler Wirtschaftsprüfung, for the year-end audit of Fernhill GmbH.\n\n'
        f'- Revenue recognised in Q3 2026 (2026-07-01 to 2026-09-30, UTC), net of VAT: **EUR {total:,.2f}**\n'
        f'- Lines: {len(lines)} (`lines.csv`: invoices, and credit notes as negative amounts)\n'
        '- Source: the client\'s ERP extracts of 2026-10-05 and 2026-10-12.\n\n'
        'Please reconcile against your own figure before the board pack is issued; we are happy to discuss any\n'
        'difference.\n', encoding='utf-8')
    return total, len(lines)


def main(root):
    invoices, credit_notes = build()
    write(Path(root), invoices, credit_notes)


if __name__ == '__main__':
    main(sys.argv[1])
