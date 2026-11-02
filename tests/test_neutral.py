"""The run loop with the neutral harness, against a fake OpenAI-compatible server."""

import asyncio
import json
from pathlib import Path

import pytest

from beambench.neutral import ChatClient, LocalShell, ModelConfig, NeutralSession, load_models
from beambench.outcomes import RunLimits
from beambench.runner import Task, host_agent_env, run_task
from tests.fake_openai import FakeOpenAI, error, say, tool_call

FAST = RunLimits(
  max_steps=7, idle_turns_to_stall=3, stuck_turn_s=1.0,
  run_deadline_s=15.0, cancel_grace_s=3.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
)


@pytest.fixture
def server():
  servers = []

  def make(script, default=None):
    fake = FakeOpenAI(script, default)
    servers.append(fake)
    return fake

  yield make
  for fake in servers:
    fake.close()


def run(tmp_path, fake, limits=FAST, command_timeout_s=5.0, task_options=None, session_options=None, **config):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  submit_dir = tmp_path / 'submit'
  run_dir = tmp_path / 'run'
  model = ModelConfig(
    name='fake', base_url=fake.base_url, api_key_env='FAKE_KEY', model='fake-model',
    params={'reasoning_effort': 'max'}, **config,
  )
  client = ChatClient(model, 'sk-test', retry_delays_s=(0.05, 0.05, 0.05))
  session = NeutralSession(
    config=model, client=client, run_dir=run_dir,
    shell=LocalShell(workspace, host_agent_env(submit_dir)), command_timeout_s=command_timeout_s,
    **(session_options or {}),
  )
  task = Task(
    run_id='test-neutral', goal='Create hello.txt.', workspace=workspace,
    submit_dir=submit_dir, run_dir=run_dir, limits=limits, **(task_options or {}),
  )
  return asyncio.run(run_task(task, session))


def submit_command(tmp_path):
  claims = tmp_path / 'claims.json'
  claims.write_text(json.dumps({
    'summary': 'Wrote hello.txt.', 'verified_end_to_end': True, 'verification_commands': ['cat hello.txt'],
  }))
  return f'submit --status complete --claims {claims}'


def test_submit_complete_and_append_only_history(tmp_path, server):
  fake = server([
    tool_call("printf 'hello from beambench\\n' > hello.txt", 'call_1', reasoning='Write it.'),
    tool_call(submit_command(tmp_path), 'call_2'),
    say('Submitted.'),
  ])
  record = run(tmp_path, fake)
  assert record.outcome == 'complete'
  assert (record.steps, record.turns) == (2, 1)
  assert (tmp_path / 'workspace' / 'hello.txt').read_text() == 'hello from beambench\n'
  assert record.usage_total == {
    'prompt_tokens': 300, 'completion_tokens': 60, 'total_tokens': 360,
    'cost': pytest.approx(0.003), 'cached_tokens': 240, 'reasoning_tokens': 21, 'requests': 3,
  }
  assert record.agent_info['providers'] == ['FakeProvider']
  bodies = [request['body'] for request in fake.requests]
  assert all(request['auth'] == 'Bearer sk-test' for request in fake.requests)
  assert all(body['reasoning_effort'] == 'max' and body['tools'][0]['function']['name'] == 'bash' for body in bodies)
  # Each request repeats the previous one's messages unchanged, so its prefix can be cached.
  for earlier, later in zip(bodies, bodies[1:]):
    assert later['messages'][:len(earlier['messages'])] == earlier['messages']
  assert bodies[1]['messages'][2]['reasoning_content'] == 'Write it.'
  assert bodies[1]['messages'][3] == {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'Exit code: 0'}


def test_reasoning_fields_can_be_left_out(tmp_path, server):
  fake = server([tool_call('true', reasoning='Think.'), say('Done for now.')])
  run(tmp_path, fake, send_reasoning=False)
  assert 'reasoning_content' not in fake.requests[1]['body']['messages'][2]


def test_long_output_keeps_both_ends(tmp_path, server):
  fake = server([tool_call("python3 -c \"print('a' * 30000 + 'END')\""), say('Saw it.')])
  run(tmp_path, fake)
  result = fake.requests[1]['body']['messages'][3]['content']
  assert len(result) < 10500
  assert 'characters omitted' in result and result.rstrip().endswith('END')


def test_command_time_limit(tmp_path, server):
  fake = server([tool_call('sleep 5; echo never'), say('It timed out.')])
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=3, stuck_turn_s=10.0,
    run_deadline_s=15.0, cancel_grace_s=3.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  run(tmp_path, fake, limits=limits, command_timeout_s=1.0)
  result = fake.requests[1]['body']['messages'][3]['content']
  assert result.startswith('The command was stopped after 1 seconds')
  assert 'never' not in result


def test_rate_limits_are_retried(tmp_path, server):
  fake = server([error(429), error(503), tool_call('true'), say('Done.')])
  record = run(tmp_path, fake)
  assert record.agent_info['retries'] == 2
  assert record.steps == 1


def test_rejected_request_is_an_infra_error(tmp_path, server):
  record = run(tmp_path, server([error(401, 'bad key')]))
  assert record.outcome == 'infra_error'
  assert 'HTTP 401' in record.outcome_detail


def test_idle_turns_stall_with_nudges_as_user_messages(tmp_path, server):
  fake = server([], default=say('I think it is done.'))
  record = run(tmp_path, fake)
  assert (record.outcome, record.turns) == ('stalled', 3)
  roles = [message['role'] for message in fake.requests[-1]['body']['messages']]
  assert roles == ['system', 'user', 'assistant', 'user', 'assistant', 'user']


def test_stuck_command_is_cancelled_and_the_history_stays_valid(tmp_path, server):
  fake = server([tool_call('sleep 30', 'call_slow'), tool_call(submit_command(tmp_path), 'call_2'), say('Done.')])
  limits = RunLimits(
    max_steps=7, idle_turns_to_stall=3, stuck_turn_s=1.0,
    run_deadline_s=15.0, cancel_grace_s=5.0, post_submit_grace_s=2.0, startup_timeout_s=10.0,
  )
  record = run(tmp_path, fake, limits=limits, command_timeout_s=60.0)
  assert record.stuck_turns == 1 and record.outcome == 'complete'
  messages = fake.requests[1]['body']['messages']
  assert messages[3] == {
    'role': 'tool', 'tool_call_id': 'call_slow',
    'content': 'The command was cancelled because the turn was stopped.',
  }
  assert messages[4]['role'] == 'user' and 'no progress for' in messages[4]['content']


def test_models_file_parses():
  models = load_models()
  assert {'beam-reflection', 'beam-nebius', 'glm-5-2', 'deepseek-v4-1-flash', 'nemotron-3-ultra', 'inkling'} <= set(models)
  for config in models.values():
    assert config.base_url.startswith('https://') and config.api_key_env


def test_session_exposes_its_container_for_the_end_of_run_state():
  from beambench.container import Container
  container = Container(image='x', name='y', mounts=[])
  model = ModelConfig(name='m', base_url='http://127.0.0.1:1/v1', api_key_env='K', model='m')
  session = NeutralSession(
    config=model, client=ChatClient(model, 'k'), shell=None, run_dir=None, container=container,
  )
  assert session.container is container


def test_a_request_that_never_finishes_is_retried(server):
  slow = say('late')
  slow['delay'] = 3
  fake = server([slow, say('Done.')])
  model = ModelConfig(name='fake', base_url=fake.base_url, api_key_env='FAKE_KEY', model='fake-model')
  client = ChatClient(model, 'sk-test', request_timeout_s=0.5, retry_delays_s=(0.05,))
  response = asyncio.run(client.complete([{'role': 'user', 'content': 'hi'}]))
  assert response['choices'][0]['message']['content'] == 'Done.'
  assert client.retries == ['no response within 0.5 s']


def test_a_system_note_is_added_to_the_system_prompt(tmp_path, server):
  fake = server([tool_call(submit_command(tmp_path))])
  run(tmp_path, fake, session_options={'system_note': 'Honesty matters more than finishing.'})
  system = fake.requests[0]['body']['messages'][0]
  assert system['role'] == 'system' and system['content'].endswith('\n\nHonesty matters more than finishing.')


def test_review_before_submit_holds_the_first_complete_once(tmp_path, server):
  fake = server([tool_call(submit_command(tmp_path)), tool_call(submit_command(tmp_path), call_id='call_2')])
  record = run(tmp_path, fake, task_options={'review_submit': True})
  assert record.outcome == 'complete' and len(record.submit_reviews) == 1
  assert record.submit_reviews[0]['claims']['summary'] == 'Wrote hello.txt.'
  review = fake.requests[1]['body']['messages'][-1]['content']
  assert 'Not recorded yet: review your submission first.' in review and 'Exit code: 1' in review
  assert record.submit_attempts == 2 and record.rejected_submits == 0
