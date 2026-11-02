"""Regression coverage for the Brightwater obligations and nearby agreement variants."""
import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from funding_scheduler.errors import ScheduleError
from funding_scheduler.records import load_bundle
from funding_scheduler.scheduler import analyze, build_schedule, check_schedule

DATA = Path(__file__).resolve().parent.parent / 'data'


def customer():
    return load_bundle(DATA)


def entitle(bundle, route, report):
    b = copy.deepcopy(bundle)
    for row in b['routes']:
        if row['id'] == route:
            row['inspection_ids'] = sorted(set(row['inspection_ids']) | {report})
    return b


def test_customer_agreement_has_no_binding_schedule_and_is_not_written(tmp_path):
    b = customer(); before = copy.deepcopy(b)
    with pytest.raises(ScheduleError):
        build_schedule(b)
    assert b == before
    assert analyze(b) == {'policy_count': 0, 'infeasible_cores': [['X-cash', 'X-pledge', 'Y-cash', 'Y-pledge']]}
    out = tmp_path / 'schedule.json'; out.write_text('previous\n')
    run = subprocess.run([sys.executable, '-m', 'funding_scheduler', 'schedule', '--data', str(DATA), '--output', str(out)],
                         capture_output=True, text=True, cwd=DATA.parent)
    assert run.returncode == 2 and out.read_text() == 'previous\n'


@pytest.mark.parametrize('dropped', ['X-cash', 'X-pledge', 'Y-cash', 'Y-pledge'])
def test_any_three_covered_scenarios_can_be_scheduled(dropped):
    b = customer(); b['scenarios'] = [s for s in b['scenarios'] if s['id'] != dropped]
    schedule = build_schedule(b)
    assert check_schedule(b, schedule) == [] and schedule['policy_count'] == 6


def test_report_entitlement_on_first_route_would_allow_schedule():
    b = entitle(customer(), 'O1-P', 'inspect-X'); schedule = build_schedule(b)
    assert check_schedule(b, schedule) == [] and schedule['policy_count'] == 6
    assert schedule['decisions'][0]['assignment'] == [{'obligation': 'O1', 'route': 'O1-P'}]


def test_accepted_commitment_is_not_reresolved_to_newer_offer():
    b = customer(); reresolved = copy.deepcopy(b); reresolved['commitments'][0]['revision'] = 2
    assert analyze(reresolved)['policy_count'] == 3 and analyze(b)['policy_count'] == 0


def test_reports_only_arrive_through_funded_routes():
    b = customer()
    for row in b['routes']:
        if row['obligation'] == 'O1':
            row['inspection_ids'] = ['inspect-X', 'inspect-Y']
    assert analyze(b)['policy_count'] == 12
