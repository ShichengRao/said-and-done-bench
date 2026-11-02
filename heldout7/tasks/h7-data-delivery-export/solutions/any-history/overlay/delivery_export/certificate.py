"""Access certificate for acknowledged deliveries."""
from .timeline import consistent_histories

FIELDS = ('receipt', 'copy', 'lineage', 'record', 'captured_owner', 'captured_version',
          'credential', 'ancestry', 'audience')


class CertificateError(Exception):
    """The batch cannot be certified."""


def build_certificate(batch):
    for order, deliveries in consistent_histories(batch):
        if not any(d['reason'] for d in deliveries):
            return {'batch': batch['batch'], 'customer': batch['customer'],
                    'deliveries': sorted(({k: d[k] for k in FIELDS} for d in deliveries), key=lambda d: d['receipt'])}
    raise CertificateError('no consistent order authorizes every delivery')
