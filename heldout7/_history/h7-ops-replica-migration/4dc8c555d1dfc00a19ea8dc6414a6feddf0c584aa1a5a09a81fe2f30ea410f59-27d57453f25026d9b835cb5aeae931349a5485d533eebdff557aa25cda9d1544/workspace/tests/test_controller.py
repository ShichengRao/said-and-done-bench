import pytest

from migration.controller import MigrationController
from migration.errors import MigrationError
from migration.planner import plan_migration


def small_fleet():
    return {'fleet_id': 'sample', 'at': 5,
            'nodes': {'a': {'rack': 'r', 'zone': 'z0', 'capacity': 2}, 'b': {'rack': 'r', 'zone': 'z1', 'capacity': 2}},
            'rack_capacity': {'r': 4}, 'groups': {'g': {'quorum': 1, 'min_zones': 1}},
            'units': {'u': {'group': 'g', 'size': 2, 'allowed_final': ['b']}},
            'initial': {'positions': {'u': 'a'}, 'images': {'u': 'old'}}, 'target': {'u': 'b'},
            'links': [{'id': 'ab', 'revision': 1, 'source': 'a', 'target': 'b', 'enabled': True, 'valid_from': 0, 'valid_to': 9}]}


def test_direct_move_reaches_target():
    fleet = small_fleet()
    actions = plan_migration(fleet)
    controller = MigrationController(fleet)
    controller.run(actions)
    assert controller.at_target() and actions[0] == ['start', 'u', 'b']


def test_commit_requires_ready_copy():
    controller = MigrationController(small_fleet())
    controller.apply(['start', 'u', 'b'])
    with pytest.raises(MigrationError):
        controller.apply(['commit', 'u', 'b'])
    assert controller.state()['shadow'] == ['u', 'b', 'copying']


def test_staged_copy_counts_against_rack():
    fleet = small_fleet(); fleet['rack_capacity']['r'] = 3
    with pytest.raises(MigrationError):
        MigrationController(fleet).apply(['start', 'u', 'b'])
