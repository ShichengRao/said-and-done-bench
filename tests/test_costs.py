"""Time and cost per run, from each agent's own usage names."""

import pytest

from beambench.costs import load_prices, normalize, run_cost

PRICES = load_prices()


def record(agent, usage, model, worker=None, minutes=10):
  return {
    'task': {'agent': agent, 'worker': {'model': 'Beam-1.0-501B-A23B'} if worker else None},
    'agent_info': {'model': model} if agent != 'mirror' else {'models': {'currentModelId': model}},
    'usage_total': usage, 'worker': worker,
    'started_at': '2026-10-27T10:00:00+00:00', 'ended_at': f'2026-10-27T10:{minutes:02d}:00+00:00',
  }


def test_each_agents_usage_maps_onto_the_same_fields():
  assert normalize('neutral', {'prompt_tokens': 1000, 'cached_tokens': 800, 'completion_tokens': 50}) == {
    'input': 200, 'cached_input': 800, 'cache_write': 0, 'output': 50}
  assert normalize('codex', {'input_tokens': 1000, 'cached_input_tokens': 900, 'output_tokens': 70}) == {
    'input': 100, 'cached_input': 900, 'cache_write': 0, 'output': 70}
  assert normalize('claude', {'input_tokens': 10, 'cache_read_input_tokens': 900, 'cache_creation_input_tokens': 90,
                              'output_tokens': 40}) == {'input': 10, 'cached_input': 900, 'cache_write': 90, 'output': 40}
  assert normalize('mirror', {'inputTokens': 67990, 'cachedReadTokens': 49792, 'outputTokens': 3632}) == {
    'input': 18198, 'cached_input': 49792, 'cache_write': 0, 'output': 3632}


def test_billed_cost_wins_and_estimates_use_list_prices():
  billed = run_cost(record('claude', {'input_tokens': 10, 'output_tokens': 10, 'cost_usd': 1.25}, 'claude-opus-5-5'), PRICES)
  assert billed.cost_usd == 1.25 and billed.billed and billed.minutes == 10
  codex = run_cost(record('codex', {'input_tokens': 1_000_000, 'cached_input_tokens': 800_000, 'output_tokens': 10_000},
                          'gpt-6.1-sol'), PRICES)
  assert codex.cost_usd == pytest.approx(0.2 * 2.00 + 0.8 * 0.10 + 0.01 * 10.00) and not codex.billed


def test_a_brain_runs_cost_adds_its_workers_tokens_at_the_workers_price():
  run = record(
    'claude', {'output_tokens': 1, 'cost_usd': 2.00}, 'claude-opus-5-5',
    worker={'usage': {'prompt_tokens': 1_000_000, 'cached_tokens': 0, 'completion_tokens': 1_000_000}},
  )
  cost = run_cost(run, PRICES)
  assert cost.cost_usd == pytest.approx(2.00 + 0.25 + 1.00) and not cost.billed
  assert cost.worker_tokens['output'] == 1_000_000


def test_a_scaffolds_unbilled_calls_are_priced_with_the_measured_cache_share():
  prices = {'beam': {'input': 0.25, 'cached_input': 0.05, 'output': 1.00}}
  record = {'task': {'agent': 'neutral'}, 'agent_info': {'model': 'beam'},
            'usage_total': {'prompt_tokens': 0, 'completion_tokens': 0},
            'scaffold': {'usage': {'prompt_tokens': 1_000_000, 'completion_tokens': 100_000}}}
  from beambench import costs
  share = costs.SCAFFOLD_CACHED_SHARE
  expected = ((1 - share) * 0.25 + share * 0.05) + 0.1
  assert abs(costs.run_cost(record, prices).cost_usd - expected) < 1e-6
  billed = {**record, 'usage_total': {'prompt_tokens': 10, 'completion_tokens': 1, 'cost': 0.5},
            'scaffold': {'usage': {**record['scaffold']['usage'], 'cost': 0.2}}}
  assert costs.run_cost(billed, prices).cost_usd == 0.7  # Billed calls keep their bill.


def test_a_neutral_run_whose_record_has_no_usage_takes_its_transcripts(tmp_path):
  import json
  response = lambda cost, cached: {'response': {'usage': {
    'prompt_tokens': 1000, 'completion_tokens': 100, 'cost': cost, 'prompt_tokens_details': {'cached_tokens': cached}}}}
  (tmp_path / 'neutral.jsonl').write_text('\n'.join(json.dumps(line) for line in (
    response(0.01, 0), {'command': 'ls'}, {'tool_result': {'content': 'ok'}}, response(0.02, 800))) + '\n')
  record = {'task': {'agent': 'neutral'}, 'usage_total': {}, 'agent_info': {'model': 'moonshotai/kimi-k3'}}
  assert run_cost(record, load_prices()).cost_usd == 0.0  # The record alone: nothing.
  cost = run_cost(record, load_prices(), tmp_path)
  assert cost.billed and cost.cost_usd == pytest.approx(0.03)
  assert cost.tokens == {'input': 1200, 'cached_input': 800, 'cache_write': 0, 'output': 200}
  recorded = {**record, 'usage_total': {'prompt_tokens': 5, 'completion_tokens': 1, 'cost': 0.5}}
  assert run_cost(recorded, load_prices(), tmp_path).cost_usd == 0.5  # A record's own usage wins.
