import copy
from pathlib import Path

import pytest

from rollout.capacity import profile_problems
from rollout.catalog import load_config
from rollout.planner import PlacementError, candidate_plans, choose_links

DATA = Path(__file__).resolve().parent.parent / 'data'


def lease(config, profile_id, node, extra):
    config = copy.deepcopy(config)
    for profile in config['profiles']:
        if profile['id'] == profile_id:
            profile['leases'][node] += extra
    return config


def test_each_replica_carries_full_units():
    config = load_config(DATA)
    gamma = [p for p in config['profiles'] if p['id'] == 'gamma-outage'][0]
    assert profile_problems({'contacts': 'cd', 'events': 'cd'}, config, gamma)  # d lease 1, two full copies


def test_out_of_region_link_is_never_used():
    config = load_config(DATA)
    plans = list(candidate_plans(config, config['profiles'][:1]))
    assert plans and all('af' not in plan.values() for plan in plans)


def test_supplied_configuration_has_no_committed_plan():
    with pytest.raises(PlacementError):
        choose_links(load_config(DATA))


def test_one_extra_unit_on_node_d_during_gamma_outage():
    plan = choose_links(lease(load_config(DATA), 'gamma-outage', 'd', 1))
    assert plan == {'accounts': 'bd', 'contacts': 'cd', 'events': 'ae', 'tickets': 'be'}


def test_plan_must_hold_in_every_profile_at_once():
    config = load_config(DATA)
    gamma_only = list(candidate_plans(config, [p for p in config['profiles'] if p['id'] == 'gamma-outage']))
    assert gamma_only == [{'accounts': 'be', 'contacts': 'cd', 'events': 'ae', 'tickets': 'be'}]
