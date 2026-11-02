"""Access certificate for acknowledged deliveries."""
from .authority import AuthorityState
from .timeline import merge_exports

FIELDS = ('receipt', 'copy', 'lineage', 'record', 'captured_owner', 'captured_version',
          'credential', 'ancestry', 'audience')


class CertificateError(Exception):
    """The batch cannot be certified."""


def build_certificate(batch):
    state = AuthorityState(batch['records'], batch['credentials'])
    deliveries = []
    for event in merge_exports(batch):
        entry = state.apply(event)
        if entry is not None:
            deliveries.append(entry)
    problems = ['%s: %s' % (d['receipt'], d['reason']) for d in deliveries if d['reason']]
    if problems:
        raise CertificateError('; '.join(problems))
    return {'batch': batch['batch'], 'customer': batch['customer'],
            'deliveries': sorted(({k: d[k] for k in FIELDS} for d in deliveries), key=lambda d: d['receipt'])}
