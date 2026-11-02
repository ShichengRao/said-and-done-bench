from itertools import product
from .errors import CloseError


def allocate(captures, refunds, fixed, controls, merchants):
    identities = sorted(captures)
    choices = [[fixed[i]] if i in fixed else sorted(captures[i]['eligible']) for i in identities]
    for combination in product(*choices):
        totals = {m: {'gross_cents': 0, 'refund_cents': 0} for m in merchants}
        for identity, merchant in zip(identities, combination):
            totals[merchant]['gross_cents'] += captures[identity]['amount_cents']
            totals[merchant]['refund_cents'] += refunds.get(identity, 0)
        if all(totals[m][name] == amount for m, row in controls.items() for name, amount in row.items()):
            return dict(zip(identities, combination))
    raise CloseError('Merchant close validation failed for the supplied records')
