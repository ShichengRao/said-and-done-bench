"""The run loop with an ACP session, against a scripted fake agent: one scenario per outcome."""

import asyncio
import json
import sys
import tarfile
from pathlib import Path

from beambench.container import Container
from beambench.mirror import AcpSession
from beambench.outcomes import RunLimits
from beambench.runner import Task, approve_matching, host_agent_env, run_task

ROOT = Path(__file__).resolve().parent.parent
FAKE_AGENT = Path(__file__).resolve().parent / 'fake_acp_agent.py'
FAST = RunLimits(
  max_steps=7,
  idle_turns_to_stall=3,
  stuck_turn_s=1.0,
  run_deadline_s=10.0,
  cancel_grace_s=1.0,
  post_submit_grace_s=2.0, startup_timeout_s=10.0,
)


def run(tmp_path, scenario, limits=FAST, **overrides):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  submit_dir = tmp_path / 'submit'
  env = host_agent_env(submit_dir)
  env['FAKE_ACP_SCENARIO'] = scenario
  env['FAKE_ACP_SUBMIT'] = str(ROOT / 'container' / 'submit')
  run_dir = tmp_path / 'run'
  task = Task(
    run_id=f'test-{scenario}',
    goal='Create hello.txt.',
    workspace=workspace,
    submit_dir=submit_dir,
    run_dir=run_dir,
    limits=limits,
    **overrides,
  )
  session = AcpSession(
    [sys.executable, str(FAKE_AGENT)],
    agent_cwd=str(workspace),
    run_dir=run_dir,
    env=env,
    cwd=workspace,
  )
  return asyncio.run(run_task(task, session))


def snapshot_names(tmp_path):
  with tarfile.open(tmp_path / 'run' / 'snapshot.tar.gz') as tar:
    return set(tar.getnames())


def test_submit_complete(tmp_path):
  record = run(tmp_path, 'submit')
  assert record.outcome == 'complete'
  assert record.submit['claims']['verification_commands'] == ['cat hello.txt']
  assert (record.steps, record.approvals, record.turns) == (2, 1, 1)
  assert 'workspace/hello.txt' in snapshot_names(tmp_path)
  saved = json.loads((tmp_path / 'run' / 'record.json').read_text())
  assert saved['outcome'] == 'complete'
  assert saved['agent_info']['agentInfo']['name'] == 'fake-acp-agent'


def test_submit_blocked(tmp_path):
  assert run(tmp_path, 'blocked').outcome == 'blocked'


def test_malformed_submit_is_rejected_then_retried(tmp_path):
  record = run(tmp_path, 'badsubmit')
  assert record.outcome == 'complete'
  assert (record.submit_attempts, record.rejected_submits) == (2, 1)
  transcript = (tmp_path / 'run' / 'acp.jsonl').read_text()
  assert 'submit exited 1: Submission rejected' in transcript


def test_idle_turns_stall_after_three(tmp_path):
  record = run(tmp_path, 'idle')
  assert record.outcome == 'stalled'
  assert (record.turns, record.nudges) == (3, 2)
  assert record.usage_total == {'inputTokens': 300, 'outputTokens': 60, 'cachedReadTokens': 240}
  assert record.snapshot is not None


def test_step_cap(tmp_path):
  record = run(tmp_path, 'steps')
  assert record.outcome == 'step_cap'
  assert record.steps > FAST.max_steps


def test_stuck_turn_is_cancelled_and_nudged_until_run_deadline(tmp_path):
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=10, stuck_turn_s=1.0,
    run_deadline_s=2.5, cancel_grace_s=1.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  record = run(tmp_path, 'hang', limits)
  assert record.outcome == 'timeout'
  assert record.stuck_turns == 2
  assert record.stop_reasons == ['stuck', 'stuck']


def test_agent_that_ignores_cancel_is_an_infra_error(tmp_path):
  record = run(tmp_path, 'ignore_cancel')
  assert record.outcome == 'infra_error'
  assert "didn't stop when its turn was cancelled" in record.outcome_detail


def test_turn_error_after_tool_calls_is_nudged(tmp_path):
  record = run(tmp_path, 'tool_errors')
  assert (record.outcome, record.turns, record.agent_errors) == ('complete', 2, 1)
  assert record.stop_reasons[0].startswith('error: Reached the maximum of 5 exceptions')


def test_crash_is_an_infra_error(tmp_path):
  record = run(tmp_path, 'crash')
  assert record.outcome == 'infra_error'
  assert 'AgentExited' in record.outcome_detail


def test_approval_policy_denies_unmatched_tool_calls(tmp_path):
  record = run(tmp_path, 'deny', approve=approve_matching(r'submit'))
  assert (record.approvals, record.denials) == (0, 1)
  assert record.outcome == 'stalled'


def test_kickoff_reaches_the_agent(tmp_path):
  run(tmp_path, 'submit')
  first = (tmp_path / 'run' / 'acp.jsonl').read_text().splitlines()
  prompts = [
    json.loads(line)['msg'] for line in first
    if json.loads(line).get('msg', {}).get('method') == 'session/prompt'
  ]
  text = prompts[0]['params']['prompt'][0]['text']
  assert text.startswith('GOAL: Create hello.txt.')
  assert 'submit --status complete --claims /tmp/claims.json' in text


def test_container_passes_secrets_by_name_and_records_the_agent_pid(tmp_path):
  container = Container(
    image='beambench-task:dev',
    name='beambench-x',
    mounts=[(tmp_path / 'w', '/workspace')],
    env_from_host=['REFLECTION_API_KEY'],
    env={'DISABLE_AUTOUPDATER': '1'},
  )
  run = container.run_command()
  assert run[run.index('--env') + 1] == 'REFLECTION_API_KEY'
  assert 'DISABLE_AUTOUPDATER=1' in run
  assert f'{tmp_path / "w"}:/workspace' in run
  assert run[-3:] == ['beambench-task:dev', 'sleep', 'infinity']
  exec_ = container.exec_command(['mirror', 'acp'])
  assert exec_[:4] == ['docker', 'exec', '--interactive', 'beambench-x']
  assert exec_[-2:] == ['mirror', 'acp'] and '/tmp/beambench-agent.pid' in exec_[-4]
