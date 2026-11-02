"""The run loop with a Codex session, against a fake `codex` on this machine."""

import asyncio
import json
import sys
from pathlib import Path

from beambench.codex import CodexSession, codex_args
from beambench.outcomes import RunLimits
from beambench.runner import Task, host_agent_env, run_task

ROOT = Path(__file__).resolve().parent.parent
FAKE_CODEX = Path(__file__).resolve().parent / 'fake_codex.py'
FAST = RunLimits(
  max_steps=7, idle_turns_to_stall=3, stuck_turn_s=1.0,
  run_deadline_s=10.0, cancel_grace_s=2.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
)


def run(tmp_path, scenario, limits=FAST):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  submit_dir = tmp_path / 'submit'
  run_dir = tmp_path / 'run'
  codex_home = run_dir / 'codex'
  auth_file = tmp_path / 'stored' / 'auth.json'
  auth_file.parent.mkdir()
  auth_file.write_text('{"original": true}')
  env = host_agent_env(submit_dir)
  env.update(
    FAKE_CODEX_SCENARIO=scenario,
    FAKE_CODEX_STATE=str(tmp_path / 'fake-state'),
    FAKE_CODEX_SUBMIT=str(ROOT / 'container' / 'submit'),
    CODEX_HOME=str(codex_home),
  )
  task = Task(
    run_id=f'test-{scenario}', goal='Create hello.txt.', workspace=workspace,
    submit_dir=submit_dir, run_dir=run_dir, limits=limits,
  )
  session = CodexSession(
    run_dir=run_dir, executable=[sys.executable, str(FAKE_CODEX)], env=env, cwd=workspace,
    codex_home=codex_home, auth_file=auth_file,
  )
  return asyncio.run(run_task(task, session))


def calls(tmp_path):
  return [json.loads(line) for line in (tmp_path / 'fake-state' / 'calls.jsonl').read_text().splitlines()]


def test_submit_complete(tmp_path):
  record = run(tmp_path, 'submit')
  assert record.outcome == 'complete'
  assert (record.steps, record.turns) == (2, 1)  # The file change and the submit command.
  assert record.usage_total == {'input_tokens': 10, 'cached_input_tokens': 4, 'output_tokens': 5}
  assert record.agent_info['warnings'] == ['Code Mode is unavailable in this fake.']
  assert calls(tmp_path)[0]['argv'][:2] == ['exec', '--json']


def test_nudges_resume_the_thread(tmp_path):
  record = run(tmp_path, 'two_turns')
  assert (record.outcome, record.turns) == ('complete', 2)
  # item_1 appears in both turns; keyed by turn, it counts twice.
  assert record.steps == 3
  second = calls(tmp_path)[1]['argv']
  assert second[:2] == ['exec', 'resume']
  assert second[-2:] == [record.agent_info['thread_id'], '-']


def test_failed_turn_is_an_infra_error(tmp_path):
  record = run(tmp_path, 'failed')
  assert record.outcome == 'infra_error'
  assert 'usage limit reached' in record.outcome_detail


def test_idle_turns_stall(tmp_path):
  assert run(tmp_path, 'idle').outcome == 'stalled'


def test_stuck_turn_is_interrupted(tmp_path):
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=10, stuck_turn_s=1.0, run_deadline_s=2.5,
    cancel_grace_s=2.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  record = run(tmp_path, 'hang', limits)
  assert record.outcome == 'timeout' and record.stuck_turns >= 1


def test_sign_in_copy_is_removed_and_unchanged_auth_is_kept(tmp_path):
  run(tmp_path, 'submit')
  assert not (tmp_path / 'run' / 'codex' / 'auth.json').exists()
  assert (tmp_path / 'stored' / 'auth.json').read_text() == '{"original": true}'


def test_refreshed_sign_in_replaces_the_stored_one(tmp_path):
  record = run(tmp_path, 'refresh')
  assert record.agent_info['auth_refreshed'] is True
  assert (tmp_path / 'stored' / 'auth.json').read_text() == '{"refreshed": true}'
  assert not (tmp_path / 'run' / 'codex' / 'auth.json').exists()


def test_args_match_the_benchmark_setup():
  first = codex_args(None, model='gpt-6.1-sol', effort='max')
  assert '--dangerously-bypass-approvals-and-sandbox' in first and '--strict-config' in first
  assert 'model_reasoning_effort="max"' in first and 'web_search="disabled"' in first
  disabled = {first[i + 1] for i, arg in enumerate(first) if arg == '--disable'}
  assert {'apps', 'plugins', 'browser_use', 'computer_use', 'image_generation'} <= disabled
  assert first[-1] == '-'
  assert codex_args('t1', model='gpt-6.1-sol', effort='max')[-2:] == ['t1', '-']
