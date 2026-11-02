"""Access certificate for acknowledged deliveries.

A certificate is issued only when the batch evidence establishes it: every
history consistent with the exports must authorize every receipt and agree on
the captured provenance being certified.
"""
import json

from .timeline import consistent_histories

FIELDS = ('receipt', 'copy', 'lineage', 'record', 'captured_owner', 'captured_version',
          'credential', 'ancestry', 'audience')


class CertificateError(Exception):
    """The batch cannot be certified."""


def _view(deliveries):
    return sorted(({key: d[key] for key in FIELDS} for d in deliveries), key=lambda d: d['receipt'])


def build_certificate(batch):
    views = {}
    count = 0
    for order, deliveries in consistent_histories(batch):
        count += 1
        problems = [d for d in deliveries if d['reason']]
        if problems:
            first = problems[0]
            raise CertificateError(
                'the evidence allows the order %s, in which receipt %s (copy %s, credential %s) is not authorized: %s'
                % (' '.join(order), first['receipt'], first['copy'], first['credential'], first['reason']))
        views[json.dumps(_view(deliveries), sort_keys=True)] = order
    if not count:
        raise CertificateError('no ordering of the exports is consistent with the recorded outcomes')
    if len(views) != 1:
        raise CertificateError('captured provenance differs between orders allowed by the evidence')
    return {'batch': batch['batch'], 'customer': batch['customer'], 'deliveries': json.loads(next(iter(views)))}
