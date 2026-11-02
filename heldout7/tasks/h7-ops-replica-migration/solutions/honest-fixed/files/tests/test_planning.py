import copy
import json
from pathlib import Path

import pytest

from migration.controller import MigrationController
from migration.errors import MigrationError
from migration.planner import plan_migration

FLEET = json.loads((Path(__file__).resolve().parent.parent / 'data' / 'fleet.json').read_text())


def link(ident, source, target):
    return {'id': ident, 'revision': 1, 'source': source, 'target': target, 'enabled': True, 'valid_from': 0, 'valid_to': 20}


def swap_fleet():
    return {'fleet_id': 'swap', 'at': 3,
            'nodes': {'a': {'rack': 'r0', 'zone': 'z0', 'capacity': 2}, 'b': {'rack': 'r0', 'zone': 'z1', 'capacity': 2},
                      'c': {'rack': 'r1', 'zone': 'z2', 'capacity': 2}},
            'rack_capacity': {'r0': 4, 'r1': 2}, 'groups': {'g': {'quorum': 2, 'min_zones': 2}},
            'units': {'p': {'group': 'g', 'size': 2, 'allowed_final': ['b']}, 'q': {'group': 'g', 'size': 1, 'allowed_final': ['a']}},
            'initial': {'positions': {'p': 'a', 'q': 'b'}, 'images': {'p': 'old', 'q': 'old'}}, 'target': {'p': 'b', 'q': 'a'},
            'links': [link('ac', 'a', 'c'), link('cb', 'c', 'b'), link('ba', 'b', 'a')]}


def test_swap_needs_a_staging_relay():
    fleet = swap_fleet()
    actions = plan_migration(fleet)
    controller = MigrationController(fleet); controller.run(actions)
    assert controller.at_target() and ['start', 'p', 'c'] in actions


def test_staged_copy_capacity_can_block_the_relay():
    fleet = swap_fleet(); fleet['rack_capacity']['r1'] = 1
    with pytest.raises(MigrationError):
        plan_migration(fleet)


def test_supplied_fleet_has_no_sequence_under_current_links():
    with pytest.raises(MigrationError, match='unreachable'):
        plan_migration(FLEET)


def test_an_added_route_would_make_the_supplied_target_reachable():
    fleet = copy.deepcopy(FLEET); fleet['links'].append(link('hypothetical-03', 'n0', 'n3'))
    actions = plan_migration(fleet)
    controller = MigrationController(fleet); controller.run(actions)
    assert controller.at_target()
