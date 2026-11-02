"""The brain/worker configuration's worker server, against a scripted model API."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.fake_openai import FakeOpenAI, say, tool_call

WORKER = Path(__file__).resolve().parent.parent / 'container' / 'beam_worker.py'


class Server:
  def __init__(self, tmp_path, fake, max_commands=60):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'submit').write_text(f'#!/bin/sh\necho "$@" > {tmp_path}/submitted; cat "$4" >> {tmp_path}/submitted; echo accepted\n')
    (bin_dir / 'submit').chmod(0o755)
    self.workspace = tmp_path / 'workspace'
    self.workspace.mkdir()
    env = {
      **os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
      'BEAMBENCH_WORKER_BASE_URL': fake.base_url, 'BEAMBENCH_WORKER_MODEL': 'beam',
      'BEAMBENCH_WORKER_PARAMS': json.dumps({'reasoning_effort': 'max'}), 'BEAMBENCH_WORKER_KEY_ENV': 'WORKER_KEY',
      'WORKER_KEY': 'worker-secret', 'ANTHROPIC_API_KEY': 'brain-secret',
      'BEAMBENCH_WORKER_WORKSPACE': str(self.workspace), 'BEAMBENCH_WORKER_MAX_COMMANDS': str(max_commands),
    }
    self.proc = subprocess.Popen(
      [sys.executable, str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env,
    )
    self.next_id = 0

  def request(self, method, params=None):
    self.next_id += 1
    self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.next_id, 'method': method, 'params': params or {}}) + '\n')
    self.proc.stdin.flush()
    notes = []
    while True:
      message = json.loads(self.proc.stdout.readline())
      if message.get('id') == self.next_id:
        return message['result'], notes
      notes.append(message)

  def close(self):
    self.proc.stdin.close()
    self.proc.wait(timeout=10)


def test_delegation_runs_commands_and_reports_them(tmp_path):
  fake = FakeOpenAI([
    tool_call('echo hello > note.txt && cat note.txt'),
    tool_call('echo "keys:[$ANTHROPIC_API_KEY][$WORKER_KEY]"', call_id='call_2'),
    say('Wrote note.txt; it says hello.'),
  ])
  server = Server(tmp_path, fake)
  try:
    init, _ = server.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}})
    tools, _ = server.request('tools/list')
    result, notes = server.request('tools/call', {
      'name': 'delegate', 'arguments': {'instructions': 'Write hello to note.txt.'}, '_meta': {'progressToken': 7},
    })
    submitted, _ = server.request('tools/call', {
      'name': 'submit', 'arguments': {'status': 'complete', 'claims': {'summary': 'done'}},
    })
  finally:
    server.close()
    fake.close()
  assert init['serverInfo']['name'] == 'worker'
  assert {tool['name'] for tool in tools['tools']} == {'delegate', 'submit'}
  text = result['content'][0]['text']
  assert not result['isError'] and text.startswith('Wrote note.txt; it says hello.')
  assert '`echo hello > note.txt && cat note.txt` -> exit 0' in text
  assert (server.workspace / 'note.txt').read_text() == 'hello\n'
  assert [note['params']['progress'] for note in notes] == [1, 2]
  # The worker's model got the instruction, its tool, and its key; its commands got no keys.
  first = fake.requests[0]
  assert first['auth'] == 'Bearer worker-secret' and first['body']['reasoning_effort'] == 'max'
  assert first['body']['messages'][-1] == {'role': 'user', 'content': 'Write hello to note.txt.'}
  assert first['body']['tools'][0]['function']['name'] == 'bash'
  assert 'keys:[][]' in fake.requests[2]['body']['messages'][-1]['content']
  assert submitted['content'][0]['text'] == 'accepted'
  assert (tmp_path / 'submitted').read_text().startswith('--status complete --claims ')
  assert '"summary": "done"' in (tmp_path / 'submitted').read_text()


def test_the_command_budget_is_shared_across_delegations(tmp_path):
  fake = FakeOpenAI([
    tool_call('true'), say('first done'),
    tool_call('echo should-not-run', call_id='call_9'), say('budget gone'),
  ])
  server = Server(tmp_path, fake, max_commands=1)
  try:
    server.request('initialize', {'protocolVersion': '2025-06-18'})
    server.request('tools/call', {'name': 'delegate', 'arguments': {'instructions': 'one'}})
    second, _ = server.request('tools/call', {'name': 'delegate', 'arguments': {'instructions': 'two'}})
  finally:
    server.close()
    fake.close()
  assert 'budget for this task (1 commands) is used up' in fake.requests[3]['body']['messages'][-1]['content']
  assert 'Commands the worker ran:\n(none)' in second['content'][0]['text']
  # The conversation carries over: the second delegation sees the first.
  assert {'role': 'user', 'content': 'one'} in fake.requests[2]['body']['messages']
