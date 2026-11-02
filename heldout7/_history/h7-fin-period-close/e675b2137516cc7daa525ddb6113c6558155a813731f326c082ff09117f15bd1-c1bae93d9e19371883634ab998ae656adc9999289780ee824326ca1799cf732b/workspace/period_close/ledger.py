from collections import defaultdict
from .errors import CloseError
from .processor import current_events


def current_position(batch):
    selected = current_events(batch['deliveries'], batch['period']['as_of'])
    captures = {identity: value for (kind, identity), value in selected.items() if kind == 'capture'}
    refunds = defaultdict(int)
    for (kind, identity), value in selected.items():
        if kind == 'refund':
            if value['capture'] not in captures:
                raise CloseError('Refund has no current capture')
            refunds[value['capture']] += value['amount_cents']
    fixed = {}
    for posting in batch['journal']:
        if posting['signed'] and posting['closed']:
            capture, merchant = posting['capture'], posting['merchant']
            if capture not in captures or merchant not in captures[capture]['eligible']:
                raise CloseError('Posted capture identity differs')
            if capture in fixed and fixed[capture] != merchant:
                raise CloseError('Conflicting posted merchants')
            fixed[capture] = merchant
    return captures, dict(refunds), fixed
