"""A scripted stand-in for `claude -p --output-format stream-json`.

FAKE_CLAUDE_SCENARIO picks the behavior; each call appends its arguments to
$FAKE_CLAUDE_STATE/calls.jsonl, which also tells it which turn it's on.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCENARIO = os.environ.get('FAKE_CLAUDE_SCENARIO', 'submit')
STATE = Path(os.environ['FAKE_CLAUDE_STATE'])
SUBMIT = os.environ['FAKE_CLAUDE_SUBMIT']
USAGE = {'input_tokens': 10, 'output_tokens': 5, 'cache_read_input_tokens': 3, 'server_tool_use': {}}


def emit(event):
  sys.stdout.write(json.dumps(event) + '\n')
  sys.stdout.flush()


def tool_use(call_id, name, tool_input):
  emit({'type': 'assistant', 'message': {'content': [
    {'type': 'tool_use', 'id': call_id, 'name': name, 'input': tool_input},
  ]}})


def tool_result(call_id, text):
  emit({'type': 'user', 'message': {'content': [
    {'type': 'tool_result', 'tool_use_id': call_id, 'content': text},
  ]}})


def say(text):
  emit({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}})


def result(subtype='success', is_error=False, text='done'):
  emit({'type': 'result', 'subtype': subtype, 'is_error': is_error, 'result': text, 'usage': USAGE})


def submit():
  claims = {'summary': 'Wrote hello.txt.', 'verified_end_to_end': True, 'verification_commands': ['cat hello.txt']}
  with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(claims, f)
  tool_use('toolu_submit', 'Bash', {'command': f'submit --status complete --claims {f.name}'})
  done = subprocess.run(
    [sys.executable, SUBMIT, '--status', 'complete', '--claims', f.name],
    capture_output=True, text=True, check=False,
  )
  tool_result('toolu_submit', done.stdout)


def main():
  signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
  STATE.mkdir(parents=True, exist_ok=True)
  calls = STATE / 'calls.jsonl'
  with calls.open('a') as f:
    f.write(json.dumps({'argv': sys.argv[1:], 'prompt': sys.stdin.read()}) + '\n')
  turn = len(calls.read_text().splitlines())
  emit({'type': 'system', 'subtype': 'init', 'model': 'fake-opus', 'claude_code_version': '0.0.0',
        'permissionMode': 'bypassPermissions', 'tools': ['Bash', 'Write']})

  if SCENARIO == 'submit' or (SCENARIO == 'two_turns' and turn == 2):
    tool_use('toolu_write', 'Write', {'file_path': 'hello.txt', 'content': 'hello from beambench\n'})
    Path('hello.txt').write_text('hello from beambench\n')
    tool_result('toolu_write', 'ok')
    submit()
    say('Submitted.')
    result()
  elif SCENARIO == 'two_turns':
    tool_use(f'toolu_look_{turn}', 'Bash', {'command': 'ls'})
    tool_result(f'toolu_look_{turn}', '')
    say('Looked around; will continue.')
    result()
  elif SCENARIO == 'error':
    result(is_error=True, text='Claude AI usage limit reached')
  elif SCENARIO == 'busy' and turn == 1:
    # Works for longer than the stuck-turn limit, but never goes quiet for that long.
    for i in range(5):
      time.sleep(0.4)
      tool_use(f'toolu_busy_{i}', 'Bash', {'command': 'sleep 0.4'})
      tool_result(f'toolu_busy_{i}', '')
    result()
  elif SCENARIO == 'hang':
    while True:
      time.sleep(0.05)
  else:
    say('Thinking it over.')
    result()


if __name__ == '__main__':
  main()
