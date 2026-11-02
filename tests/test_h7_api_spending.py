import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('h7_api_spending',
    Path(__file__).resolve().parents[1]/'heldout7/_shared/api_spending.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


def test_streamed_message_is_counted_once_at_final_usage(tmp_path):
    path = tmp_path/'claude.jsonl'
    rows = [{'type':'assistant','message':{'id':'same-response','usage':{
        'input_tokens':1000,'output_tokens':out,'cache_creation_input_tokens':2000,
        'cache_read_input_tokens':3000,'cache_creation':{'ephemeral_1h_input_tokens':1000}}}}
        for out in (1, 500, 500)]
    path.write_text('\n'.join(map(json.dumps, rows))+'\n{"in_flight":')
    result = budget.log_cost(path)
    assert result['cost_usd'] == pytest.approx(.0276)
    assert not result['closed']


def test_cli_reported_usage_keeps_costs_absent_from_message_stream(tmp_path):
    path = tmp_path/'claude.jsonl'
    path.write_text(json.dumps({'type':'result','total_cost_usd':1.25})+'\n')
    assert budget.log_cost(path)['cost_usd'] == 1.25
    assert budget.log_cost(path)['closed']


def test_missing_final_usage_does_not_release_a_job(tmp_path):
    path = tmp_path/'claude.jsonl'
    path.write_text(json.dumps({'type':'result','is_error':True})+'\n')
    assert not budget.log_cost(path)['closed']


def test_native_wrapped_usage_is_counted(tmp_path):
    path=tmp_path/'claude.jsonl'
    rows=[{'t':1,'turn':1,'event':{'type':'assistant','message':{'id':'a',
        'usage':{'input_tokens':1000,'output_tokens':2000}}}},
        {'t':2,'turn':1,'event':{'type':'result','total_cost_usd':.075}}]
    path.write_text('\n'.join(map(json.dumps,rows)))
    assert budget.log_cost(path)=={'cost_usd':.075,'closed':True,
        'cost_kind':'CLI result or conservative token estimate; excludes unknown failed-request billing'}


def test_native_turn_completion_keeps_reservation_until_run_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(budget,'ROOT',tmp_path)
    plan=tmp_path/'heldout7/API_EXECUTION_PLAN.json';plan.parent.mkdir()
    plan.write_text(json.dumps({'authoring_session_caps_usd':{}}))
    leases=tmp_path/'runs/h7-api-budget/leases';leases.mkdir(parents=True)
    log=tmp_path/'runs/candidate/claude.jsonl';log.parent.mkdir()
    log.write_text(json.dumps({'type':'result','total_cost_usd':1.2})+'\n')
    (leases/'candidate.json').write_text(json.dumps({'job':'calibration-example','limit_usd':2,'log':'runs/candidate/claude.jsonl'}))
    assert budget.snapshot()['active_reservation_usd']==pytest.approx(11.4)
    (log.parent/'record.json').write_text(json.dumps({'ended_at':'2026-11-02T01:00:00Z'}))
    assert budget.snapshot()['active_reservation_usd']==0
