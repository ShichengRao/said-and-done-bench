import copy
import json
from pathlib import Path

import pytest

from delivery_export.batch import load_batch
from delivery_export.certificate import CertificateError, build_certificate
from delivery_export.timeline import consistent_histories

DATA = Path(__file__).resolve().parent.parent / 'data'


def batch_with(extra):
    batch = load_batch(DATA)
    batch = copy.deepcopy(batch)
    batch['ordering'] += [{'earlier': a, 'later': b} for a, b in extra]
    return batch


def test_supplied_batch_is_not_established():
    histories = list(consistent_histories(load_batch(DATA)))
    authorized = [o for o, d in histories if not any(x['reason'] for x in d)]
    assert (len(histories), len(authorized)) == (1266, 12)
    with pytest.raises(CertificateError):
        build_certificate(load_batch(DATA))


def test_derived_copy_keeps_original_provenance():
    certificate = build_certificate(batch_with([('b2', 'a3'), ('c3', 'b1'), ('b4', 'c4')]))
    assert certificate['deliveries'] == [{
        'receipt': 'b4', 'copy': 'b3', 'lineage': ['b1', 'b3'], 'record': 'account', 'captured_owner': 'alpha',
        'captured_version': 0, 'credential': 'c3', 'ancestry': ['c2', 'c3'], 'audience': 'auditors'}]


def test_copy_after_owner_return_certifies_version_two():
    certificate = build_certificate(batch_with([('a3', 'b1'), ('b4', 'c4')]))
    assert certificate['deliveries'][0]['captured_version'] == 2


def test_later_grant_does_not_authorize_earlier_delivery():
    with pytest.raises(CertificateError):
        build_certificate(batch_with([('b4', 'c3')]))


def test_cli_preserves_existing_certificate(tmp_path):
    from delivery_export.cli import main
    target = tmp_path / 'certificate.json'
    target.write_text('{"previous": true}\n')
    assert main(['--batch', str(DATA), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
