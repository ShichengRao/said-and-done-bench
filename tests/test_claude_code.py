"""The run loop with a Claude Code session, against a fake `claude` on this machine."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from beambench.claude_code import ClaudeCodeSession, claude_flags
from beambench.outcomes import RunLimits
from beambench.runner import Task, host_agent_env, run_task

ROOT = Path(__file__).resolve().parent.parent
FAKE_CLAUDE = Path(__file__).resolve().parent / 'fake_claude.py'
FAST = RunLimits(
  max_steps=7, idle_turns_to_stall=3, stuck_turn_s=1.0,
  run_deadline_s=10.0, cancel_grace_s=2.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
)


def run(tmp_path, scenario, limits=FAST):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  submit_dir = tmp_path / 'submit'
  run_dir = tmp_path / 'run'
  env = host_agent_env(submit_dir)
  env.update(
    FAKE_CLAUDE_SCENARIO=scenario,
    FAKE_CLAUDE_STATE=str(tmp_path / 'fake-state'),
    FAKE_CLAUDE_SUBMIT=str(ROOT / 'container' / 'submit'),
  )
  task = Task(
    run_id=f'test-{scenario}', goal='Create hello.txt.', workspace=workspace,
    submit_dir=submit_dir, run_dir=run_dir, limits=limits,
  )
  session = ClaudeCodeSession(
    run_dir=run_dir, executable=[sys.executable, str(FAKE_CLAUDE)], env=env, cwd=workspace
  )
  return asyncio.run(run_task(task, session))


def calls(tmp_path):
  return [json.loads(line) for line in (tmp_path / 'fake-state' / 'calls.jsonl').read_text().splitlines()]


def test_submit_complete(tmp_path):
  record = run(tmp_path, 'submit')
  assert record.outcome == 'complete'
  assert (record.steps, record.turns) == (2, 1)
  assert record.agent_info['init']['model'] == 'fake-opus'
  assert record.usage_total['output_tokens'] == 5
  assert (tmp_path / 'workspace' / 'hello.txt').exists()
  assert calls(tmp_path)[0]['prompt'].startswith('GOAL: Create hello.txt.')


def test_nudges_resume_the_same_session(tmp_path):
  record = run(tmp_path, 'two_turns')
  assert (record.outcome, record.turns, record.nudges) == ('complete', 2, 1)
  first, second = (call['argv'] for call in calls(tmp_path))
  session_id = record.agent_info['session_id']
  assert first[first.index('--session-id') + 1] == session_id
  assert second[second.index('--resume') + 1] == session_id
  assert calls(tmp_path)[1]['prompt'].startswith('Continue working toward the goal (autonomous turn 2).')


def test_idle_turns_stall(tmp_path):
  record = run(tmp_path, 'idle')
  assert (record.outcome, record.turns) == ('stalled', 3)


def test_reported_error_is_an_infra_error(tmp_path):
  record = run(tmp_path, 'error')
  assert record.outcome == 'infra_error'
  assert 'usage limit reached' in record.outcome_detail


def test_stuck_turn_is_interrupted_and_resumed(tmp_path):
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=10, stuck_turn_s=1.0,
    run_deadline_s=2.5, cancel_grace_s=2.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  record = run(tmp_path, 'hang', limits)
  assert record.outcome == 'timeout'
  assert record.stuck_turns >= 1
  argvs = [call['argv'] for call in calls(tmp_path)]
  assert '--session-id' in argvs[0] and all('--resume' in argv for argv in argvs[1:])


def test_busy_turn_longer_than_the_stuck_limit_is_not_cancelled(tmp_path):
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=1, stuck_turn_s=1.0,
    run_deadline_s=10.0, cancel_grace_s=2.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  record = run(tmp_path, 'busy', limits)
  assert (record.stuck_turns, record.steps) == (0, 5)
  assert record.stop_reasons[0] == 'success'


def test_flags_match_the_benchmark_setup():
  flags = claude_flags('abc', first_turn=False, model='claude-opus-5-5', effort='max')
  assert flags[flags.index('--permission-mode') + 1] == 'bypassPermissions'
  assert flags[flags.index('--disallowedTools') + 1] == 'WebSearch,WebFetch'
  assert '--strict-mcp-config' in flags
  assert flags[flags.index('--effort') + 1] == 'max'
  assert flags[-2:] == ['--resume', 'abc']


def test_cost_per_turn_is_the_increase_in_claude_codes_running_total(tmp_path):
  session = ClaudeCodeSession(run_dir=tmp_path)
  turns = []
  for total in (0.0269, 0.0455, 0.0455):
    session._result = {'subtype': 'success', 'usage': {'output_tokens': 5}, 'total_cost_usd': total}
    turns.append(session.end_turn(0, cancelled=False).usage['cost_usd'])
  assert turns == pytest.approx([0.0269, 0.0186, 0.0])
