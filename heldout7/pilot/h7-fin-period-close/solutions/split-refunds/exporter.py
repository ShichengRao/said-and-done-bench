import json
import os
import tempfile
from pathlib import Path
from .errors import CloseError
from .ledger import current_position
from .allocation import allocate


def build_close(batch):
    captures, refunds, fixed = current_position(batch)
    gross = sum(row['amount_cents'] for row in captures.values())
    refunded = sum(refunds.values())
    totals = {'gross_cents': gross, 'refund_cents': refunded, 'net_cents': gross-refunded}
    if totals != batch['bank']:
        raise CloseError('Processor position does not match the bank settlement')
    period = batch['period']
    gross_controls = {m: {'gross_cents': row['gross_cents']} for m, row in batch['controls'].items()}
    assignment = allocate(captures, refunds, fixed, gross_controls, period['merchants'])
    merchants = {m: dict(gross_cents=0, refund_cents=0, net_cents=0, capture_count=0) for m in period['merchants']}
    lines = []
    for identity, merchant in sorted(assignment.items()):
        amount = captures[identity]['amount_cents']; refunded = refunds.get(identity, 0)
        row = dict(capture=identity, merchant=merchant, gross_cents=amount, refund_cents=refunded, net_cents=amount-refunded)
        lines.append(row)
        for key in ['gross_cents', 'refund_cents', 'net_cents']:
            merchants[merchant][key] += row[key]
        merchants[merchant]['capture_count'] += 1
    for merchant, control in batch['controls'].items():
        merchants[merchant]['refund_cents'] = control['refund_cents']
        merchants[merchant]['net_cents'] = merchants[merchant]['gross_cents'] - control['refund_cents']
    remainder = next(m for m in merchants if m not in batch['controls'])
    merchants[remainder]['refund_cents'] = totals['refund_cents'] - sum(row['refund_cents'] for m, row in merchants.items() if m != remainder)
    merchants[remainder]['net_cents'] = merchants[remainder]['gross_cents'] - merchants[remainder]['refund_cents']
    return dict(batch=period['batch'], currency=period['currency'], as_of=period['as_of'], totals=totals, merchants=merchants, allocations=lines)


def write_close(batch, output):
    package = build_close(batch)
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.close-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(package, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return package
