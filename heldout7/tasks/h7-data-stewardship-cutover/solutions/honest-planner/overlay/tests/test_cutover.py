import copy
import json
from pathlib import Path

import pytest

from stewardship.ledger import load, resolve
from stewardship.planner import PlanningError, build_model, legal_paths, plan

DATA = Path(__file__).resolve().parent.parent / 'data'


def test_revision_selection_respects_approval_cutoff_and_phase():
    cutover, entries = load(DATA)
    assert resolve(entries, 'capacity', 1, 10)['alpha'] == {'units': 3}
    grants = resolve(entries, 'handoff', 1, 10)
    assert grants['tickets-migration-transfer']['active'] is False
    assert resolve(entries, 'handoff', 1, 12)['tickets-migration-transfer']['active'] is True


def test_supplied_ledger_paths():
    model = build_model(*load(DATA))
    paths = {g['id']: legal_paths(g, 3) for g in model['groups']}
    assert paths['accounts'] == [['alpha', 'alpha', 'beta'], ['beta', 'beta', 'beta']]
    assert paths['tickets'] == [['beta', 'alpha', 'alpha'], ['beta', 'beta', 'beta']]


def test_supplied_ledger_has_no_valid_assignment():
    with pytest.raises(PlanningError):
        plan(*load(DATA))


def test_handoff_only_applies_at_its_boundary():
    cutover, entries = load(DATA)
    entries = copy.deepcopy(entries)
    entries.append({'kind': 'handoff', 'entity': 'accounts-early', 'revision': 1, 'recorded': 9, 'effective': 0,
                    'approved': True, 'value': {'record': 'accounts', 'boundary': 0, 'from': 'alpha', 'to': 'beta', 'active': True}})
    result = plan(cutover, entries)
    owners = {g['id']: g['owners'] for g in result['groups']}
    assert owners['accounts'] == ['alpha', 'beta', 'beta'] and owners['tickets'] == ['beta', 'alpha', 'alpha']


def test_reapproved_late_transfer_inside_baseline():
    cutover, entries = load(DATA)
    result = plan(dict(cutover, approval_cutoff=12), entries)
    assert {g['id']: g['owners'] for g in result['groups']}['tickets'] == ['beta', 'beta', 'alpha']
