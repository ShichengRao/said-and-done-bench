import json

from delivery_export.batch import load_batch
from delivery_export.cli import main
from delivery_export.certificate import build_certificate


def write_batch(root, events, ordering=()):
    (root / 'exports').mkdir(parents=True)
    (root / 'batch.json').write_text(json.dumps({'batch': 'T-1', 'customer': 'Example', 'exports': ['svc']}))
    (root / 'records.json').write_text(json.dumps({'doc': {'owner': 'x', 'version': 2}}))
    (root / 'credentials.json').write_text(json.dumps({
        'slots': {'main': {'generation': 0, 'current': 'k0'}},
        'issued': [{'id': 'k0', 'slot': 'main', 'parent': None, 'owner': 'x', 'issuer': 'x',
                    'audience': 'team', 'delegable': False}]}))
    (root / 'exports' / 'svc.json').write_text(json.dumps({'service': 'svc', 'sealed': True, 'events': events}))
    (root / 'ordering.json').write_text(json.dumps({'attestations': [dict(earlier=a, later=b) for a, b in ordering]}))
    return root


def test_single_service_delivery(tmp_path):
    events = [
        {'id': 'cp', 'logged_at': '1', 'kind': 'copy', 'source': {'kind': 'record', 'id': 'doc'}, 'slot': 'main'},
        {'id': 'rc', 'logged_at': '2', 'kind': 'receipt', 'copy': 'cp', 'audience': 'team'},
    ]
    certificate = build_certificate(load_batch(write_batch(tmp_path, events)))
    assert certificate['deliveries'] == [{
        'receipt': 'rc', 'copy': 'cp', 'lineage': ['cp'], 'record': 'doc', 'captured_owner': 'x',
        'captured_version': 2, 'credential': 'k0', 'ancestry': ['k0'], 'audience': 'team'}]


def test_recorded_failure_must_be_possible(tmp_path):
    # Version 2 matches, so a recorded failure contradicts the batch: nothing is certified.
    events = [{'id': 'oc', 'logged_at': '1', 'kind': 'owner_change', 'record': 'doc',
               'expected_version': 2, 'new_owner': 'y', 'succeeded': False}]
    target = tmp_path / 'out' / 'certificate.json'
    assert main(['--batch', str(write_batch(tmp_path / 'batch', events)), '--output', str(target)]) != 0
    assert not target.exists()
