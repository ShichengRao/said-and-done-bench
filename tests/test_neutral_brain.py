"""The neutral harness as a brain: read tools here, delegate and submit through the worker server."""

import asyncio
import json
import os
import sys
from pathlib import Path

from beambench.neutral import ChatClient, LocalShell, ModelConfig
from beambench.neutral_brain import BrainSession, McpWorker, read_command
from tests.fake_openai import USAGE, FakeOpenAI, say, tool_call

WORKER = Path(__file__).resolve().parent.parent / 'container' / 'beam_worker.py'


def call(name, arguments, call_id='call_1'):
  message = {'role': 'assistant', 'content': None, 'tool_calls': [{
    'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)},
  }]}
  return {'body': {'choices': [{'message': message, 'finish_reason': 'tool_calls'}], 'usage': USAGE}}


def test_read_commands_quote_their_arguments():
  assert read_command('read_file', {'path': "a'; rm -rf /"}).endswith(" 'a'\"'\"'; rm -rf /'")
  assert read_command('read_file', {'path': '-f'}).endswith(' ./-f')
  assert "-e 'x|y'" in read_command('grep', {'pattern': 'x|y', 'include': '*.py'})
  assert read_command('grep', {}) is None and read_command('bash', {'command': 'ls'}) is None
  assert 'offset' not in read_command('read_file', {'path': 'f', 'offset': 'soon'})  # Bad numbers fall back.


def test_a_brain_reads_delegates_and_submits_through_the_worker(tmp_path):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  (workspace / 'README.md').write_text('first line\nsecond line\n')
  bin_dir = tmp_path / 'bin'
  bin_dir.mkdir()
  (bin_dir / 'submit').write_text(f'#!/bin/sh\necho "$@" > {tmp_path}/submitted; cat "$4" >> {tmp_path}/submitted; echo accepted\n')
  (bin_dir / 'submit').chmod(0o755)
  worker_model = FakeOpenAI([tool_call('echo done > note.txt'), say('Wrote note.txt.')])
  brain_model = FakeOpenAI([
    call('read_file', {'path': 'README.md', 'offset': 2}),
    call('delegate', {'instructions': 'Write note.txt.'}, call_id='call_2'),
    call('submit', {'status': 'complete', 'claims': {'summary': 'Wrote note.txt.'}}, call_id='call_3'),
    say('Submitted.'),
  ])
  env = {
    **os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
    'BEAMBENCH_WORKER_BASE_URL': worker_model.base_url, 'BEAMBENCH_WORKER_MODEL': 'beam',
    'BEAMBENCH_WORKER_KEY_ENV': 'WORKER_KEY', 'WORKER_KEY': 'worker-secret',
    'BEAMBENCH_WORKER_WORKSPACE': str(workspace),
  }
  config = ModelConfig(name='brain', base_url=brain_model.base_url, api_key_env='BRAIN_KEY', model='beam-brain')
  session = BrainSession(
    config=config, client=ChatClient(config, 'brain-secret'), shell=LocalShell(workspace),
    run_dir=tmp_path, worker=McpWorker([sys.executable, str(WORKER)], env=env),
  )
  activity = []
  session.on_activity = lambda: activity.append(1)

  async def go():
    await session.start()
    try:
      return await session.prompt('Write a note, then submit.')
    finally:
      await session.close()

  end = asyncio.run(go())
  brain_model.close()
  worker_model.close()
  assert end.stop_reason == 'stop'
  assert (workspace / 'note.txt').read_text() == 'done\n'
  assert 'complete' in (tmp_path / 'submitted').read_text()
  tools = [tool['function']['name'] for tool in brain_model.requests[0]['body']['tools']]
  assert tools == ['read_file', 'grep', 'glob', 'delegate', 'submit']
  replies = [message['content'] for message in brain_model.requests[-1]['body']['messages'] if message['role'] == 'tool']
  assert replies[0].startswith('Exit code: 0') and '2\tsecond line' in replies[0] and 'first line' not in replies[0]
  assert 'Wrote note.txt.' in replies[1] and 'echo done > note.txt' in replies[1]
  assert 'accepted' in replies[2]
  assert brain_model.requests[0]['body']['messages'][0]['content'].startswith('You are an autonomous software engineering agent leading')
  assert activity  # Progress from the worker counts as activity.
