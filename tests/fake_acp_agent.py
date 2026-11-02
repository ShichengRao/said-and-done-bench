"""A scripted ACP agent for tests. FAKE_ACP_SCENARIO picks its behavior.

It runs the real container/submit command (FAKE_ACP_SUBMIT), so tests cover
the whole submit path, environment included.
"""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading

SCENARIO = os.environ.get('FAKE_ACP_SCENARIO', 'submit')
SUBMIT = os.environ.get('FAKE_ACP_SUBMIT', 'submit')
GOOD_CLAIMS = {
  'summary': 'Wrote hello.txt.',
  'verified_end_to_end': True,
  'verification_commands': ['cat hello.txt'],
}

requests = queue.Queue()
responses = {}
responses_changed = threading.Condition()
cancelled = threading.Event()
next_id = 0


def send(message):
  sys.stdout.write(json.dumps(message) + '\n')
  sys.stdout.flush()


def read_stdin():
  for line in sys.stdin:
    if not line.strip():
      continue
    message = json.loads(line)
    method = message.get('method')
    if method == 'session/cancel':
      cancelled.set()
    elif method is not None:
      requests.put(message)
    else:
      with responses_changed:
        responses[message['id']] = message
        responses_changed.notify_all()
  requests.put(None)


def call_client(method, params):
  global next_id
  next_id += 1
  request_id = f'agent-{next_id}'
  send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
  with responses_changed:
    responses_changed.wait_for(lambda: request_id in responses)
    return responses.pop(request_id)


def update(session_update, **fields):
  send({
    'jsonrpc': '2.0',
    'method': 'session/update',
    'params': {'sessionId': 's1', 'update': {'sessionUpdate': session_update, **fields}},
  })


def say(text):
  update('agent_message_chunk', content={'type': 'text', 'text': text})


def tool_call(tool_call_id, title):
  update('tool_call', toolCallId=tool_call_id, title=title, kind='execute', status='pending')


def tool_done(tool_call_id):
  update('tool_call_update', toolCallId=tool_call_id, status='completed')


def ask_permission(tool_call_id, command):
  response = call_client('session/request_permission', {
    'sessionId': 's1',
    'toolCall': {'toolCallId': tool_call_id, 'title': command, 'rawInput': {'command': command}},
    'options': [
      {'optionId': 'allow', 'name': 'Allow', 'kind': 'allow_once'},
      {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'},
    ],
  })
  return response['result']['outcome']


def run_submit(status, claims):
  with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(claims, f)
  return subprocess.run(
    [sys.executable, SUBMIT, '--status', status, '--claims', f.name],
    capture_output=True, text=True, check=False,
  )


def submit_step(tool_call_id, status, claims):
  tool_call(tool_call_id, f'submit --status {status}')
  if ask_permission(tool_call_id, f'submit --status {status}').get('optionId') == 'allow':
    # Like Mirror, report the shell process as a separate task:<n> tool call.
    tool_call(f'task:{tool_call_id}', f'submit --status {status}')
    result = run_submit(status, claims)
    say(f'submit exited {result.returncode}: {result.stdout.strip()}')
  tool_done(tool_call_id)


def run_turn(turn):
  """Play one turn and return its stop reason, or None to never answer."""
  if SCENARIO in ('submit', 'blocked', 'badsubmit') and turn == 1:
    tool_call('write', 'Write hello.txt')
    with open('hello.txt', 'w', encoding='utf-8') as f:
      f.write('hello from beambench\n')
    tool_done('write')
    if SCENARIO == 'badsubmit':
      submit_step('bad', 'done', GOOD_CLAIMS)
    submit_step('submit', 'blocked' if SCENARIO == 'blocked' else 'complete', GOOD_CLAIMS)
    return 'end_turn'
  if SCENARIO == 'tool_errors' and turn == 1:
    # Like Mirror: some tool calls fail, then the turn ends in an error.
    tool_call('slow', 'grep -r x /')
    tool_done('slow')
    return 'error'
  if SCENARIO == 'tool_errors' and turn == 2:
    submit_step('submit', 'complete', GOOD_CLAIMS)
    return 'end_turn'
  if SCENARIO == 'steps':
    for i in range(5):
      tool_call(f'step-{turn}-{i}', 'echo hi')
      tool_done(f'step-{turn}-{i}')
    return 'end_turn'
  if SCENARIO == 'hang':
    cancelled.wait()
    return 'cancelled'
  if SCENARIO == 'ignore_cancel':
    return None
  if SCENARIO == 'crash':
    sys.exit(3)
  if SCENARIO == 'deny' and turn == 1:
    tool_call('rm', 'rm -rf build')
    say(json.dumps(ask_permission('rm', 'rm -rf build')))
    tool_done('rm')
    return 'end_turn'
  say('Thinking it over.')
  return 'end_turn'


def main():
  threading.Thread(target=read_stdin, daemon=True).start()
  turn = 0
  while True:
    request = requests.get()
    if request is None:
      return
    method, params = request['method'], request.get('params') or {}
    if method == 'initialize':
      result = {
        'protocolVersion': 1,
        'agentCapabilities': {},
        'authMethods': [],
        'agentInfo': {'name': 'fake-acp-agent', 'version': '0'},
      }
    elif method == 'session/new':
      os.chdir(params['cwd'])
      result = {'sessionId': 's1'}
    elif method == 'session/prompt':
      turn += 1
      cancelled.clear()
      stop_reason = run_turn(turn)
      if stop_reason is None:
        continue
      if stop_reason == 'error':
        send({'jsonrpc': '2.0', 'id': request['id'], 'error': {
          'code': -32603, 'message': 'Reached the maximum of 5 exceptions without completing the task.'}})
        continue
      result = {'stopReason': stop_reason, 'usage': {'inputTokens': 100, 'outputTokens': 20, 'cachedReadTokens': 80}}
    else:
      send({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32601, 'message': method}})
      continue
    send({'jsonrpc': '2.0', 'id': request['id'], 'result': result})


if __name__ == '__main__':
  main()
