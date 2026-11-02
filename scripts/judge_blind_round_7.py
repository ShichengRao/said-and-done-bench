"""Blind round 7's registered judging (docs/blind-round-7-preregistration.md): one judgment from the round's frozen
judge for every run that ended "blocked" on an impossible task, then the round's own grader again.

  uv run python scripts/judge_blind_round_7.py plan      # the runs that need a judgment (no model call)
  uv run python scripts/judge_blind_round_7.py prepare   # build their packets (no model call)
  uv run python scripts/judge_blind_round_7.py judge     # one judgment per packet, in an order shuffled with seed 0
  uv run python scripts/judge_blind_round_7.py publish   # publish each valid, non-abstaining answer, then regrade

The round's scripts (heldout7/_shared) are loaded unchanged except for these substitutions, each asserted to occur
exactly once:
- run folders come from runs/main instead of the round's calibration folder;
- packets and answers go to runs/judge-h7 instead of heldout7/delivery_reviews (the round's judge validation is
  still read from there);
- this runner's own ledger and cap (CAP: the user approved up to about $15, Nov 2) replace the round's $50 ledger,
  which had about $3 left.
The prompt, schema, validator, model, effort, and token limit are the pinned ones: api_judge.config() checks every
pinned file's sha256 on disk. Nothing is retried. A run whose packet can't be built, whose judgment fails or
abstains, or that isn't published stays "pending" and doesn't count (status.json says which).
"""

import argparse
import json
import random
import subprocess
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / 'heldout7' / '_shared'
TASKS = REPO / 'heldout7' / 'tasks'
RUNS = REPO / 'runs' / 'main'
OUT = REPO / 'runs' / 'judge-h7'
LEDGER = OUT / 'budget'
CAP = 15.0
CONFIGS = ('beam-neutral', 'beam-neutral-scaffold-v5')
SEEDS = (1, 2, 3)
sys.path.insert(0, str(SHARED))
sys.path.insert(1, str(REPO))


def load(name: str, substitutions, extra=None) -> types.ModuleType:
  """heldout7/_shared/<name>.py with each (old, new) applied once; __file__ stays the frozen file's path."""
  path = SHARED / f'{name}.py'
  source = path.read_text()
  for old, new in substitutions:
    assert source.count(old) == 1, f'{name}: {old!r} occurs {source.count(old)} times'
    source = source.replace(old, new)
  module = types.ModuleType(name)
  module.__file__ = str(path)
  module.__dict__.update(extra or {})
  sys.modules[name] = module
  exec(compile(source, str(path), 'exec'), module.__dict__)
  return module


def local_budget(ledger: Path) -> dict:
  """The round's snapshot() shape, over this runner's ledger: a lease is closed once its log records a result; an
  open lease keeps its whole reservation (as the round does when usage is unknown)."""
  import api_spending
  jobs, spent, reserved = [], 0.0, 0.0
  for lease in sorted((ledger / 'leases').glob('*.json')):
    info = json.loads(lease.read_text())
    log = REPO / info['log']
    closed = log.exists() and any(json.loads(line).get('type') == 'result' for line in log.read_text().splitlines())
    if log.exists():
      spent += api_spending.log_cost(log)['cost_usd']
    if not closed:
      reserved += info['limit_usd']
    jobs.append({'job': info['job'], 'closed': closed})
  return {'cap_usd': CAP, 'recorded_or_estimated_usd': spent, 'active_reservation_usd': reserved,
          'unreserved_usd': CAP - spent - reserved, 'jobs': jobs}


def modules():
  # Addendum 2: a command the scaffold's guard blocked is logged without an exit code, since it never ran; the round's
  # reader of neutral logs (which never saw a guarded run) skips it, as the packet holds executed commands only.
  load('prepare_judge_comparison', [
    ("   if 'command' in event:\n    pending={",
     "   if 'command' in event and 'blocked' in event:pending=None\n   elif 'command' in event:\n    pending={"),
  ])
  judge = load('api_judge', [
    ("    assert packet_path.is_relative_to(ROOT/'heldout7')\n",
     "    assert packet_path.is_relative_to(ROOT/'runs/judge-h7')\n"),
    ("    assert destination.is_relative_to(ROOT/'heldout7')\n",
     "    assert destination.is_relative_to(ROOT/'runs/judge-h7')\n"),
    ("    ledger = ROOT/'runs/h7-api-budget'\n", "    ledger = ROOT/'runs/judge-h7/budget'\n"),
    ("        budget = api_spending.snapshot()\n", "        budget = LOCAL_BUDGET(ledger)\n"),
  ], {'LOCAL_BUDGET': local_budget})
  review = load('delivery_review', [
    ("OUT=ROOT/'heldout7/delivery_reviews'\n", "OUT=ROOT/'runs/judge-h7'\nVALID=ROOT/'heldout7/delivery_reviews'\n"),
    ("    run=Path(run).resolve();assert run.is_relative_to(ROOT/'runs/calibration-h7-delivery')\n",
     "    run=Path(run).resolve();assert run.is_relative_to(ROOT/'runs/main')\n"),
    ("    validation=read(OUT/'api_validation/RESULTS.json')\n",
     "    validation=read(VALID/'api_validation/RESULTS.json')\n"),
    ("    validation_review=read(OUT/'api_validation/VALIDATION_REVIEW.json')\n",
     "    validation_review=read(VALID/'api_validation/VALIDATION_REVIEW.json')\n"),
    ("    assert validation_review['results_sha256']==sha(OUT/'api_validation/RESULTS.json')\n",
     "    assert validation_review['results_sha256']==sha(VALID/'api_validation/RESULTS.json')\n"),
    ("    assert run.is_relative_to(ROOT/'runs/calibration-h7-delivery')\n    assert record['outcome']",
     "    assert run.is_relative_to(ROOT/'runs/main')\n    assert record['outcome']"),
  ])
  judge.config()  # Every pinned file's sha256, before anything else.
  return judge, review


def needing_judgment() -> list[Path]:
  """Runs of the registered setups on the impossible tasks that ended "blocked" and wait on a review."""
  found = []
  for task in sorted(path for path in TASKS.iterdir() if (path / 'task.toml').exists()):
    if json.loads((task / 'grader' / 'review_config.json').read_text())['expected_status'] != 'blocked':
      continue
    for config in CONFIGS:
      for seed in SEEDS:
        run = RUNS / task.name / config / f'seed-{seed}'
        if not (run / 'grade.json').exists():
          continue
        record = json.loads((run / 'record.json').read_text())
        if record['outcome'] == 'blocked':
          found.append(run)
  return found


def status() -> dict:
  path = OUT / 'status.json'
  return json.loads(path.read_text()) if path.exists() else {}


def save(state: dict) -> None:
  OUT.mkdir(parents=True, exist_ok=True)
  (OUT / 'status.json').write_text(json.dumps(state, indent=1, sort_keys=True) + '\n')


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
  parser.add_argument('action', choices=('plan', 'prepare', 'judge', 'publish'))
  args = parser.parse_args()
  runs = needing_judgment()
  state = status()
  if args.action == 'plan':
    for run in runs:
      print(run.relative_to(RUNS), state.get(str(run.relative_to(RUNS)), {}).get('state', 'not prepared'))
    print(f'{len(runs)} runs ended "blocked" on the impossible tasks')
    return 0
  judge, review = modules()
  if args.action == 'prepare':
    for run in runs:
      key = str(run.relative_to(RUNS))
      if key in state and state[key]['state'] != 'packet_failed':
        continue
      try:
        prepared = review.prepare(run)
        state[key] = {'state': 'prepared', 'prepared': str(prepared.relative_to(REPO))}
      except Exception as error:  # A packet over the round's limits, say: the run stays pending.
        state[key] = {'state': 'packet_failed', 'error': f'{type(error).__name__}: {error}'}
      save(state)
      print(key, state[key]['state'], flush=True)
    return 0
  if args.action == 'judge':
    waiting = sorted(key for key, entry in state.items() if entry['state'] == 'prepared')
    random.Random(0).shuffle(waiting)
    for key in waiting:
      prepared = REPO / state[key]['prepared']
      attempt = prepared.parent / 'attempt1'
      try:
        judge.run(prepared / 'packet.json', attempt)
        proposed = json.loads((attempt / 'semantic.proposed.json').read_text())
        state[key].update(state='abstained' if proposed['abstained'] else 'judged', attempt=str(attempt.relative_to(REPO)))
      except Exception as error:  # Never retried.
        state[key].update(state='judge_failed', error=f'{type(error).__name__}: {error}', attempt=str(attempt.relative_to(REPO)))
      save(state)
      print(key, state[key]['state'], flush=True)
    return 0
  for key, entry in sorted(state.items()):  # publish
    if entry['state'] != 'judged':
      continue
    published = review.publish(REPO / entry['prepared'], REPO / entry['attempt'])
    subprocess.run([sys.executable, '-m', 'beambench', 'grade', str(RUNS / key)], check=True, cwd=REPO,
                   stdout=subprocess.DEVNULL)
    grade = json.loads((RUNS / key / 'grade.json').read_text())
    entry.update(state='published', review=str(published.relative_to(REPO)),
                 semantic_review_status=grade['checks'].get('semantic_review_status'),
                 said_and_done=grade.get('said_and_done'))
    save(state)
    print(key, entry['state'], entry['semantic_review_status'], flush=True)
  return 0


if __name__ == '__main__':
  sys.exit(main())
