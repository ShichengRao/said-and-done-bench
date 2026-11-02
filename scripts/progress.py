"""A short progress summary of a batch: runs per config, outcomes, time, cost, and anything notable.

  uv run python scripts/progress.py [runs/main]

Runs on a family reported apart from the 15 tasks (the no-valid-option scenarios) get their own rows.
"""

import collections
import datetime
import json
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else 'runs/main')
REPO = Path(__file__).resolve().parent.parent
FAMILIES = {'scenarios': 'no-valid-option'}  # Folder -> family (beambench/batch.py FAMILIES).


def row_name(event):
  family = next((name for folder, name in FAMILIES.items() if (REPO / folder / event['task'] / 'task.toml').exists()), None)
  return event['config'] + (f' [{family}]' if family else '')


events = [json.loads(line) for line in (out / 'batch.jsonl').read_text().splitlines() if line.strip()]
# A run cut off by an API key's spending limit is set aside and rerun: not a result, not an infra error.
NETWORK = ('nodename nor servname', 'Name or service not known', 'Temporary failure in name resolution')
# Runs set aside and rerun (a key's spending limit, this machine's network dropping): not results.
ends = [e for e in events if e['event'] == 'end' and 'Key limit exceeded' not in str(e.get('detail'))
        and not any(sig in str(e.get('detail')) for sig in NETWORK)]
for e in ends:  # A run graded again since (a grader fix) has a newer verdict than its end event.
  grade = out / e['task'] / e['config'] / f"seed-{e['seed']}" / 'grade.json'
  if e.get('outcome') != 'infra_error' and grade.exists():
    e.update({k: v for k, v in json.loads(grade.read_text()).items()
              if k in ('said_and_done', 'verified_success', 'false_completion')})
running = subprocess.run(['pgrep', '-f', f'(beambench batch|batch_in_order.py) --out {out}'],
                         capture_output=True).returncode == 0
utc = lambda t: datetime.datetime.fromtimestamp(t, datetime.UTC)
print(f'batch {"running" if running else "NOT running"}; {len(ends)} runs finished; now {datetime.datetime.now(datetime.UTC):%H:%MZ}')
by_config = collections.defaultdict(list)
for e in ends:
  by_config[row_name(e)].append(e)
print(f'{"config":44}{"runs":>5}{"S&D":>5}{"done":>5}{"falseC":>7}{"infra":>6}{"min":>6}{"$":>8}')
for config, runs in by_config.items():
  minutes = sorted(e['seconds'] / 60 for e in runs)
  print(f'{config:44}{len(runs):>5}{sum(bool(e.get("said_and_done")) for e in runs):>5}'
        f'{sum(bool(e.get("verified_success")) for e in runs):>5}{sum(bool(e.get("false_completion")) for e in runs):>7}'
        f'{sum(e.get("outcome") == "infra_error" for e in runs):>6}{minutes[len(minutes) // 2]:>6.1f}'
        f'{sum(e.get("cost_usd") or 0 for e in runs):>8.2f}')
today = datetime.datetime.now(datetime.UTC).date()
tokens = collections.Counter()
for e in events:
  if e['event'] in ('end', 'cutoff') and utc(e['time']).date() == today:
    for queue, usage in (e.get('usage_by_queue') or {}).items():
      tokens[queue] += usage.get('output_tokens') or 0
print('output tokens today (UTC):', dict(tokens))
for e in events:
  if e['event'] in ('error', 'retry', 'cutoff', 'network_down', 'network_back', 'queue_paused', 'queue_stopped', 'budget_wait', 'budget_spent'):
    print(f'note {utc(e["time"]):%m-%d %H:%MZ}:', e['event'], {k: v for k, v in e.items() if k not in ('time', 'event', 'queue')})
last = {}  # Each cell's latest start or finish (a run cut off at a daily budget is rerun later).
for e in events:
  if e['event'] in ('start', 'end', 'cutoff'):
    last[(e['task'], e['config'], e['seed'])] = e['event']
for key in sorted(key for key, event in last.items() if event == 'start'):
  print('in progress:', *key)
