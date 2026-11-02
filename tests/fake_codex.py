"""A scripted stand-in for `codex exec --json`.

FAKE_CODEX_SCENARIO picks the behavior; each call appends its arguments to
$FAKE_CODEX_STATE/calls.jsonl, which also tells it which turn it's on.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCENARIO = os.environ.get('FAKE_CODEX_SCENARIO', 'submit')
STATE = Path(os.environ['FAKE_CODEX_STATE'])
SUBMIT = os.environ['FAKE_CODEX_SUBMIT']
THREAD = '01a16299-f201-7093-9d6b-6dd9a0397dcc'
USAGE = {'input_tokens': 10, 'cached_input_tokens': 4, 'output_tokens': 5}


def emit(event):
  sys.stdout.write(json.dumps(event) + '\n')
  sys.stdout.flush()


def item(kind, item_id, **fields):
  emit({'type': 'item.started', 'item': {'id': item_id, 'type': kind, **fields}})
  emit({'type': 'item.completed', 'item': {'id': item_id, 'type': kind, **fields}})


def submit():
  claims = {'summary': 'Wrote hello.txt.', 'verified_end_to_end': True, 'verification_commands': ['cat hello.txt']}
  with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(claims, f)
  subprocess.run([sys.executable, SUBMIT, '--status', 'complete', '--claims', f.name], check=False)
  item('command_execution', 'item_2', command=f'submit --status complete --claims {f.name}')


def main():
  signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
  STATE.mkdir(parents=True, exist_ok=True)
  calls = STATE / 'calls.jsonl'
  with calls.open('a') as f:
    f.write(json.dumps({'argv': sys.argv[1:], 'prompt': sys.stdin.read()}) + '\n')
  turn = len(calls.read_text().splitlines())
  if turn == 1:
    emit({'type': 'thread.started', 'thread_id': THREAD})
  item('error', 'item_0', message='Code Mode is unavailable in this fake.')
  emit({'type': 'turn.started'})

  if SCENARIO == 'refresh':
    (Path(os.environ['CODEX_HOME']) / 'auth.json').write_text('{"refreshed": true}')
  if SCENARIO in ('submit', 'refresh') or (SCENARIO == 'two_turns' and turn == 2):
    Path('hello.txt').write_text('hello from beambench\n')
    item('file_change', 'item_1', changes=[{'path': 'hello.txt', 'kind': 'add'}])
    submit()
    item('agent_message', 'item_3', text='Submitted.')
  elif SCENARIO == 'two_turns':
    item('command_execution', 'item_1', command='ls')
  elif SCENARIO == 'failed':
    emit({'type': 'error', 'message': 'Reconnecting... 1/5'})
    emit({'type': 'turn.failed', 'error': {'message': 'usage limit reached'}})
    return
  elif SCENARIO == 'hang':
    while True:
      time.sleep(0.05)
  else:
    item('agent_message', 'item_1', text='Thinking it over.')
  emit({'type': 'turn.completed', 'usage': USAGE})


if __name__ == '__main__':
  main()
