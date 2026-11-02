"""Run the benchmark matrix: every config on every eligible task, seed by seed.

`python -m beambench batch --out runs/main` runs each cell (task, config,
seed) of matrix.toml as `python -m beambench run` and then `grade`, into
<out>/<task>/<config>/seed-<n>, with the commands' output in seed-<n>.log
beside it. Stopping and starting again is safe: a graded run is skipped, a
recorded but ungraded one is graded, and one cut off when the batch stopped
is moved aside (seed-<n>.incomplete-<k>) and run again. An infrastructure
error is retried after a delay, once by default; each failed attempt is kept
as seed-<n>.infra-<k>.

Configs that share a queue (one provider, or one subscription) run one at a
time, and queues run side by side. Runs go in seed-major order, seed 1 of
every task and config before seed 2, so a batch stopped early still has
complete rounds. A queue can have a daily budget of output tokens or
requests, counted by UTC day as the providers count them; when the next run
might not fit, the queue waits for the next day. Several infrastructure
errors in a row (an outage, or a subscription's usage limit) pause a queue.
Every start, end, retry, and wait is a line in <out>/batch.jsonl.

The tasks are the 15 in tasks/ unless named. A family kept apart from them (FAMILIES: the no-valid-option
scenarios in scenarios/) runs only when named, `--tasks no-valid-option`, for any config; its runs share the
batch folder and the report shows them in a section of their own.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import datetime
import functools
import json
import re
import shutil
import socket
import sys
import time
import tomllib
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

from beambench import tasks

REPO = Path(__file__).resolve().parent.parent
MATRIX_FILE = REPO / 'matrix.toml'
TASKS_DIR = REPO / 'tasks'
NOT_BENCHMARK_TASKS = {'hello'}  # The integration smoke test.


@dataclasses.dataclass(frozen=True)
class Family:
  """Tasks that run like the 15 in tasks/ but live in a folder of their own, and get a section of their own in the
  report. A family is never in the default plan: `--tasks <id>` names every task in the family's folder; its task
  ids work too. Its runs go in the same batch folder as the rest (<out>/<task>/<config>/seed-<n>). in_score: the
  report also counts its runs in the headline numbers; otherwise they're reported apart, in the section only.
  only: the family is just these tasks of its folder (default: every task there). section: the report gives it a
  section of its own (the no-valid-option scenarios' outcomes); a family without one is just more tasks."""
  id: str
  label: str
  tasks_dir: Path
  in_score: bool = False
  only: tuple[str, ...] = ()
  section: bool = True

  def task_ids(self) -> list[str]:
    return [task_id for task_id in _task_ids(self.tasks_dir) if not self.only or task_id in self.only]


FAMILIES = {
  # In the score from Oct 28 (the user's decision): one Said & Done score over the 15 tasks and the 8 scenarios.
  'no-valid-option': Family('no-valid-option', 'No valid option', REPO / 'scenarios', in_score=True),
  # The held-out walls (Oct 28, the user's decision): copies of the five held-out tasks with no honest way to
  # finish, in walls/, run by every harness (the originals run only in the minimal one). Just more tasks.
  'heldout-walls': Family('heldout-walls', 'Held-out walls', REPO / 'walls', in_score=True, section=False),
}


def _task_ids(tasks_dir: Path) -> list[str]:
  return sorted(
    path.name for path in tasks_dir.iterdir()
    if (path / 'task.toml').exists() and path.name not in NOT_BENCHMARK_TASKS
  )


def family_of(task: tasks.TaskSpec) -> Family | None:
  """The family a task is reported in apart from the 15, if any."""
  return next((family for family in FAMILIES.values()
               if task.path.parent == family.tasks_dir.resolve() and (not family.only or task.id in family.only)), None)


def task_paths(names: Sequence[str], tasks_dir: Path = TASKS_DIR) -> list[Path]:
  """Task folders for task ids and family names: a family stands for all its tasks, and a task id is looked up
  in tasks_dir first, then in each family's folder."""
  paths = []
  for name in names:
    if name in FAMILIES:
      paths += [FAMILIES[name].tasks_dir / task_id for task_id in FAMILIES[name].task_ids()]
      continue
    found = [folder / name for folder in (tasks_dir, *(family.tasks_dir for family in FAMILIES.values()))
             if (folder / name / 'task.toml').exists()]
    if not found:
      raise ValueError(f'no task or family named {name!r}')
    paths.append(found[0])
  return list(dict.fromkeys(paths))


@dataclasses.dataclass(frozen=True)
class Config:
  name: str
  agent: str
  queue: str
  model_config: str | None = None  # neutral: an entry in models.toml
  model: str | None = None  # claude and codex
  effort: str | None = None
  claude_auth: str | None = None  # claude: 'api' or 'subscription'
  worker: str | None = None  # a brain (claude or neutral): the worker's entry in models.toml
  # Other queues a run also draws on (a brain's worker uses its model's
  # provider): the run holds them too, and its worker's usage counts there.
  also_uses: tuple[str, ...] = ()
  kickoff_note: str | None = None  # An extra paragraph in the first prompt (experiments).
  system_note: str | None = None  # neutral: a paragraph added to the system prompt (a mitigation).
  review_submit: bool = False  # Hold the first "complete" for one review turn (a mitigation).
  # Neutral only (scaffold.py): an independent reviewer at submit, a guard on risky commands, a submit tool.
  reviewer: bool = False
  guard: bool = False
  submit_tool: bool = False
  verifier: bool = False  # With reviewer: a fresh agent checks a copy of the work first.
  scaffold_version: int = 3  # 4: adds a progress check, and v4's verifier, reviewer, and guard.
  # Stress tests (JSON): {"off": [v5 parts switched off], "prompts": "a TOML file of reworded prompts"} (scaffold.py).
  scaffold_options: str | None = None
  variant_of: str | None = None  # For the report: the config this is a variant of (another effort, say).
  label: str | None = None  # For the report: a display name,
  # and beam, beam-mitigation, brain-worker, reference, or anchor (a model the
  # tasks were calibrated against, whose score is set by that design).
  group: str = 'reference'

  @property
  def queues(self) -> tuple[str, ...]:
    return (self.queue, *self.also_uses)

  @property
  def track(self) -> str:
    return 'neutral' if self.agent == 'neutral' else 'native'


@dataclasses.dataclass(frozen=True)
class Queue:
  name: str
  daily_output_tokens: int | None = None
  daily_requests: int | None = None
  max_cost_usd: float | None = None  # For the whole batch: API credits, say.
  parallel: int = 1  # Runs at once in this queue (a provider that tolerates several).
  # With a daily output-token budget that the provider enforces: start runs
  # until the budget is used up, rather than stopping a run's worth short, and
  # set aside the run the provider cuts off. A run that ends with an API error,
  # an agent error, or a stuck turn within this many tokens of the budget is
  # taken to have been cut off: it's neither a result nor an infra attempt, and
  # the queue waits for the next UTC day and runs the cell again.
  cutoff_margin: int = 0


@dataclasses.dataclass(frozen=True)
class Matrix:
  configs: dict[str, Config]
  queues: dict[str, Queue]
  seeds: tuple[int, ...]
  tasks: tuple[str, ...]  # Task ids or family names (FAMILIES); empty means every task in tasks/.
  run_deadline_s: float | None = None
  infra_retries: int = 1
  infra_delay_s: float = 300.0
  outage_after: int = 3  # Infrastructure errors in a row before a queue pauses.
  outage_pause_s: float = 1800.0


def _matrix_data(path: Path) -> dict:
  """A matrix file's tables. A file with `extends = "<matrix file>"` (relative to it) starts from that file's
  and overrides what it sets: seeds, tasks, [batch] options, and queues and configs field by field, so it can
  give a config a queue (and a budget) of its own without restating the config."""
  data = tomllib.loads(path.read_text())
  if (base_file := data.pop('extends', None)) is None:
    return data
  merged = _matrix_data((path.parent / base_file).resolve())
  for table in ('queues', 'configs'):
    combined = {name: dict(spec or {}) for name, spec in merged.get(table, {}).items()}
    for name, spec in data.get(table, {}).items():
      combined[name] = {**combined.get(name, {}), **(spec or {})}
    merged[table] = combined
  merged['batch'] = {**merged.get('batch', {}), **data.get('batch', {})}
  merged.update({key: data[key] for key in ('seeds', 'tasks') if key in data})
  return merged


def load_matrix(path: Path = MATRIX_FILE) -> Matrix:
  data = _matrix_data(path)
  queues = {name: Queue(name, **(spec or {})) for name, spec in data.get('queues', {}).items()}
  configs = {}
  for name, spec in data.get('configs', {}).items():
    config = Config(name, **{**spec, 'also_uses': tuple(spec.get('also_uses', ()))})
    for queue in config.queues:
      if queue not in queues:
        raise ValueError(f'config {name}: no [queues.{queue}] in {path.name}')
    if config.worker and config.agent not in ('claude', 'neutral'):
      raise ValueError(f'config {name}: only claude and neutral configs take a worker')
    if (config.agent == 'neutral') != bool(config.model_config):
      raise ValueError(f'config {name}: model_config is for neutral configs, and they need one')
    configs[name] = config
  options = data.get('batch', {})
  return Matrix(
    configs=configs,
    queues=queues,
    seeds=tuple(data.get('seeds', (1,))),
    tasks=tuple(data.get('tasks', ())),
    **options,
  )


@dataclasses.dataclass(frozen=True)
class Cell:
  task: tasks.TaskSpec
  config: Config
  seed: int

  def key(self) -> dict:
    return {'task': self.task.id, 'config': self.config.name, 'seed': self.seed}

  def run_dir(self, out: Path) -> Path:
    return out / self.task.id / self.config.name / f'seed-{self.seed}'


def plan(
  matrix: Matrix, *, tasks_dir: Path = TASKS_DIR, only_tasks: Sequence[str] = (),
  only_configs: Sequence[str] = (), seeds: Sequence[int] = (),
) -> list[Cell]:
  """Every eligible cell, seed-major: seed 1 of every task and config, then seed 2.

  Tasks: the ones named (task ids, or a family's id for all its tasks), else the matrix's, else every task in
  tasks_dir. A family is never included unless named, so the default plan is the 15 tasks alone."""
  names = list(only_tasks or matrix.tasks)
  paths = task_paths(names, tasks_dir) if names else [tasks_dir / task_id for task_id in _task_ids(tasks_dir)]
  specs = [tasks.load_task(path) for path in paths]
  configs = [matrix.configs[name] for name in only_configs] if only_configs else list(matrix.configs.values())
  return [
    Cell(spec, config, seed)
    for seed in (seeds or matrix.seeds)
    for spec in specs
    for config in configs
    if config.track in spec.tracks
  ]


def cost_usd(usage: dict | None) -> float:
  """What a run reported it cost: Claude Code with an API key, or OpenRouter."""
  usage = usage or {}
  for key in ('cost_usd', 'cost'):
    if isinstance(usage.get(key), (int, float)):
      return float(usage[key])
  return 0.0


def usage_by_queue(config: Config, record: dict) -> dict[str, dict]:
  """Each queue's share of a run: the agent's usage on its own queue, a worker's on the next."""
  def share(usage):
    usage = usage or {}
    return {'output_tokens': output_tokens(usage), 'requests': int(usage.get('requests') or 0), 'cost_usd': cost_usd(usage)}
  shares = {config.queue: share(record.get('usage_total'))}
  if record.get('scaffold'):  # The reviewer and guard call the agent's own model.
    extra = share(record['scaffold'].get('usage'))
    shares[config.queue] = {key: shares[config.queue][key] + extra[key] for key in extra}
  worker = share((record.get('worker') or {}).get('usage'))
  # A worker on the brain's own provider (no also_uses) adds to the brain's queue.
  for queue in config.also_uses or ((config.queue,) if config.worker else ()):
    held = shares.get(queue)
    shares[queue] = worker if held is None or queue in config.also_uses else {
      key: held[key] + worker[key] for key in ('output_tokens', 'requests', 'cost_usd')
    }
  return shares


def output_tokens(usage: dict | None) -> int:
  """Output tokens under whichever name the agent reports them."""
  usage = usage or {}
  for key in ('output_tokens', 'completion_tokens', 'outputTokens'):
    if isinstance(usage.get(key), (int, float)):
      return int(usage[key])
  return 0


def _read_json(path: Path) -> dict | None:
  try:
    return json.loads(path.read_text())
  except (OSError, ValueError):
    return None


# What a cell's run directory holds.
EMPTY, DONE, UNGRADED, INFRA, INCOMPLETE, STALE = 'empty', 'done', 'ungraded', 'infra_error', 'incomplete', 'stale'
GRADE_ERROR = 'grade_error'  # The grader failed; grading again may work.
# An API key's own spending limit or an empty balance: the account, not the
# provider, so it isn't an attempt, and the queue stops until it's raised.
_SPENDING_LIMIT = re.compile(r'Key limit exceeded|[Ii]nsufficient (credits|balance|funds)|HTTP 402\b')
# This machine's network dropped (bad Wi-Fi): not the provider and not the agent. Such a run isn't an
# attempt; the queue waits for the network and runs the cell again.
_NETWORK_DOWN = re.compile(
  r'nodename nor servname|Name or service not known|Temporary failure in name resolution|'
  r'Network is unreachable|No route to host|getaddrinfo failed'
)
NETWORK_RETRIES = 5  # Per cell, so a run that fails this way for some other reason still ends.


def network_failure(run_dir: Path, record: dict) -> bool:
  """Did this run end because the machine lost its network? From the error, or a native agent's egress log."""
  if record.get('outcome') != 'infra_error':
    return False
  if _NETWORK_DOWN.search(str(record.get('outcome_detail') or '')):
    return True
  egress = run_dir / 'egress' / 'requests.jsonl'
  return egress.exists() and bool(_NETWORK_DOWN.search(egress.read_text(errors='replace')))


def api_host(config: Config) -> str:
  """The host a config's model is reached at, to tell when the network is back."""
  if config.model_config:
    from beambench.neutral import load_models  # Not at import: keeps this module light.
    return urlsplit(load_models()[config.model_config].base_url).hostname or 'api.reflection.ai'
  return {'claude': 'api.anthropic.com', 'codex': 'chatgpt.com'}.get(config.agent, 'api.reflection.ai')


async def network_up(host: str) -> bool:
  try:
    await asyncio.get_running_loop().getaddrinfo(host, 443)
    return True
  except (OSError, socket.gaierror):
    return False


def fingerprint_file(cell: Cell, out: Path) -> Path:
  run_dir = cell.run_dir(out)
  return run_dir.with_name(f'{run_dir.name}.fingerprint.json')


async def fingerprint(cell: Cell, matrix: Matrix) -> dict:
  """Everything a run's result depends on besides the model's sampling: if any
  of it changes, the cell's old run no longer counts."""
  from beambench.__main__ import AGENT_IMAGES, TASK_IMAGE  # Not at import: __main__ imports this.
  from beambench.neutral import load_models

  config = cell.config
  models = load_models()
  task_image_id, agent_image_id = await _image_id(TASK_IMAGE), await _image_id(AGENT_IMAGES[config.agent])
  entry = dataclasses.asdict(models[config.model_config]) if config.model_config else None
  worker = dataclasses.asdict(models[config.worker]) if config.worker else None
  return {
    'claude_auth': config.claude_auth, 'worker_entry': worker, 'kickoff_note': config.kickoff_note,
    'system_note': config.system_note, 'review_submit': config.review_submit,
    'scaffold': [config.reviewer, config.guard, config.submit_tool, config.verifier],
    # Only when it isn't the default, so the cells run before it existed keep their fingerprints.
    **({'scaffold_version': config.scaffold_version} if config.scaffold_version != 3 else {}),
    **({'scaffold_options': config.scaffold_options} if config.scaffold_options else {}),
    'task_hash': _hashes(cell.task.path)[0],
    'harness_hash': tasks.harness_hash(),
    'task_image_id': task_image_id,
    'agent_image_id': agent_image_id,
    'agent': config.agent, 'model': config.model, 'effort': config.effort, 'model_entry': entry,
    'run_deadline_s': matrix.run_deadline_s,
  }


async def _image_id(image: str, attempts: int = 5) -> str:
  """An image's ID, retried: Docker can answer empty while it recovers (after a network drop, say), and an
  empty ID would make every finished cell look stale and record a fingerprint nothing matches."""
  for attempt in range(attempts):
    if found := await tasks.image_id(image):
      return found
    await asyncio.sleep(2 * (attempt + 1))
  raise RuntimeError(f'Docker has no ID for {image}; is Docker running?')


@functools.cache
def _hashes(task_path: Path) -> tuple[str, str]:
  spec = tasks.load_task(task_path)
  return tasks.task_hash(spec), tasks.grader_hash(spec)


def cell_state(cell: Cell, out: Path) -> str:
  run_dir = cell.run_dir(out)
  task_hash, grader_hash = _hashes(cell.task.path)
  if not run_dir.exists() or not any(run_dir.iterdir()):
    return EMPTY
  record = _read_json(run_dir / 'record.json')
  if record is None:
    return INCOMPLETE
  if (record.get('task') or {}).get('task_hash') != task_hash:
    return STALE
  if record.get('outcome') == 'infra_error':
    return INFRA
  grade = _read_json(run_dir / 'grade.json')
  if grade is None or grade.get('grader_hash') != grader_hash:
    return UNGRADED
  if 'grader_error' in (grade.get('checks') or {}):
    return GRADE_ERROR
  return DONE


def _set_aside(run_dir: Path, label: str) -> Path:
  """Move a run directory aside as <name>.<label>-<k>, keeping it for the record."""
  k = 1
  while (target := run_dir.with_name(f'{run_dir.name}.{label}-{k}')).exists():
    k += 1
  shutil.move(str(run_dir), target)
  for suffix in ('.log', '.fingerprint.json'):
    companion = run_dir.with_name(f'{run_dir.name}{suffix}')
    if companion.exists():
      shutil.move(str(companion), target.with_name(f'{target.name}{suffix}'))
  return target


def infra_attempts(cell: Cell, out: Path) -> int:
  run_dir = cell.run_dir(out)
  return len(list(run_dir.parent.glob(f'{run_dir.name}.infra-*[0-9]')))


# A launcher runs one command for a cell (`run` or `grade`) and returns its exit code.
Launcher = Callable[[Sequence[str], Path], Awaitable[int]]


async def subprocess_launcher(args: Sequence[str], log: Path) -> int:
  log.parent.mkdir(parents=True, exist_ok=True)
  with log.open('a') as out:
    out.write(f'\n$ python -m beambench {" ".join(args)}\n')
    out.flush()
    proc = await asyncio.create_subprocess_exec(
      sys.executable, '-m', 'beambench', *args, stdout=out, stderr=asyncio.subprocess.STDOUT, cwd=REPO,
    )
    try:
      return await proc.wait()
    except asyncio.CancelledError:
      # The run cleans up its containers on SIGINT; give it time to.
      proc.send_signal(2)
      try:
        await asyncio.wait_for(proc.wait(), 120)
      except TimeoutError:
        proc.kill()
      raise


def run_args(cell: Cell, run_dir: Path, matrix: Matrix) -> list[str]:
  config = cell.config
  args = ['run', '--agent', config.agent, '--task', str(cell.task.path), '--run-dir', str(run_dir)]
  if config.model_config:
    args += ['--model-config', config.model_config]
  if config.model:
    args += ['--model', config.model]
  if config.effort:
    args += ['--effort', config.effort]
  if config.claude_auth:
    args += ['--claude-auth', config.claude_auth]
  if config.worker:
    args += ['--worker', config.worker]
  if config.kickoff_note:
    args += ['--kickoff-note', config.kickoff_note]
  if config.system_note:
    args += ['--system-note', config.system_note]
  if config.review_submit:
    args += ['--review-submit']
  args += [flag for flag, on in (('--reviewer', config.reviewer), ('--guard', config.guard),
                                 ('--submit-tool', config.submit_tool), ('--verifier', config.verifier)) if on]
  if config.scaffold_version != 3:
    args += ['--scaffold-version', str(config.scaffold_version)]
  if config.scaffold_options:
    args += ['--scaffold-options', config.scaffold_options]
  if matrix.run_deadline_s:
    args += ['--run-deadline', str(matrix.run_deadline_s)]
  return args


def _next_utc_day(now: float) -> float:
  today = datetime.datetime.fromtimestamp(now, datetime.UTC).date()
  midnight = datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time(), datetime.UTC)
  return midnight.timestamp()


def _utc_day(timestamp: float) -> str:
  return datetime.datetime.fromtimestamp(timestamp, datetime.UTC).date().isoformat()


class Batch:
  def __init__(
    self, matrix: Matrix, out: Path, cells: Sequence[Cell], *,
    launch: Launcher = subprocess_launcher,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_parallel: int | None = None,
    rerun_stale: bool = False,
    fingerprint: Callable[[Cell, Matrix], Awaitable[dict]] = fingerprint,
    network_up: Callable[[str], Awaitable[bool]] = network_up,
  ):
    self.network_up = network_up
    self.matrix, self.out, self.cells = matrix, out, list(cells)
    self.launch, self.now, self.sleep = launch, now, sleep
    self.max_parallel = max_parallel
    self.rerun_stale = rerun_stale
    self.fingerprint = fingerprint
    self.events_file = out / 'batch.jsonl'
    self.events = [event for event in map(_read_line, self._lines()) if event]

  def _lines(self) -> list[str]:
    return self.events_file.read_text().splitlines() if self.events_file.exists() else []

  def log(self, event: str, **fields) -> None:
    entry = {'time': round(self.now(), 3), 'event': event, **fields}
    self.events.append(entry)
    self.out.mkdir(parents=True, exist_ok=True)
    with self.events_file.open('a') as out:
      out.write(json.dumps(entry) + '\n')
    detail = ' '.join(f'{key}={value}' for key, value in fields.items() if key not in ('queue',))
    print(f'[{time.strftime("%H:%M:%S")}] {fields.get("queue", "")} {event} {detail}', flush=True)

  async def run(self) -> None:
    queues: dict[str, list[Cell]] = {}
    for cell in self.cells:
      queues.setdefault(cell.config.queue, []).append(cell)
    total = sum(self.matrix.queues[name].parallel for name in queues)
    self._slots = asyncio.Semaphore(self.max_parallel or total or 1)
    # A run holds a slot in every queue it uses, so a config that also uses
    # another queue (a brain's worker) waits for that queue's slot too.
    self._locks = {name: asyncio.Semaphore(queue.parallel) for name, queue in self.matrix.queues.items()}
    self._running: dict[str, int] = {name: 0 for name in self.matrix.queues}
    self._finished: dict[str, int] = {name: 0 for name in self.matrix.queues}  # Runs ended so far.
    workers = []
    for name, cells in queues.items():
      queue = self.matrix.queues[name]
      shared = {'pending': collections.deque(cells), 'in_a_row': 0, 'paused_until': 0.0, 'stopped': False}
      workers += [self._worker(queue, shared) for _ in range(queue.parallel)]
    await asyncio.gather(*workers)

  async def _worker(self, queue: Queue, shared: dict) -> None:
    """One of a queue's workers: they take its cells in order and share its pauses and stops."""
    while shared['pending'] and not shared['stopped']:
      while self.now() < shared['paused_until']:
        await self.sleep(shared['paused_until'] - self.now())
      cell = shared['pending'].popleft()
      result = await self._cell(queue, cell)
      if result in ('config_error', 'budget_spent', 'spending_limit'):
        if not shared['stopped']:
          shared['stopped'] = True
          reason = {
            'config_error': f'{cell.config.name} could not start; see its log',
            'budget_spent': 'a queue it uses spent its max_cost_usd',
            'spending_limit': 'its API key hit a spending limit; raise it and run the batch again',
          }[result]
          self.log('queue_stopped', queue=queue.name, reason=reason)
        return
      shared['in_a_row'] = shared['in_a_row'] + 1 if result == INFRA else 0
      if shared['in_a_row'] >= self.matrix.outage_after:
        self.log('queue_paused', queue=queue.name, seconds=self.matrix.outage_pause_s, infra_errors_in_a_row=shared['in_a_row'])
        shared['paused_until'] = self.now() + self.matrix.outage_pause_s
        shared['in_a_row'] = 0

  async def _cell(self, queue: Queue, cell: Cell) -> str:
    run_dir, key = cell.run_dir(self.out), {**cell.key(), 'queue': queue.name}
    log = run_dir.with_name(f'{run_dir.name}.log')
    state = cell_state(cell, self.out)
    current = await self.fingerprint(cell, self.matrix)
    if state in (DONE, UNGRADED, GRADE_ERROR, INFRA):
      recorded = _read_json(fingerprint_file(cell, self.out)) or {}
      if changed := sorted(name for name in current if recorded.get(name) != current[name]):
        state = STALE
        key = {**key, 'changed': changed}
    if state == DONE:
      return DONE
    if state in (UNGRADED, GRADE_ERROR):
      await self._grade(cell, run_dir, log, key)
      return DONE
    if state == STALE:
      if not self.rerun_stale:
        self.log('stale', **key, note='run on an older version of the task, harness, image, or config; pass --rerun-stale')
        return STALE
      _set_aside(run_dir, 'stale')
    if state == INCOMPLETE:
      _set_aside(run_dir, 'incomplete')
    if state == INFRA:
      if infra_attempts(cell, self.out) + 1 > self.matrix.infra_retries:
        return 'retries_used'  # From an earlier batch; not a new error.
      _set_aside(run_dir, 'infra')
      self.log('retry', **key, after_s=self.matrix.infra_delay_s)
      await self.sleep(self.matrix.infra_delay_s)
    network_tries = 0
    while True:
      for name in cell.config.queues:
        if not await self._wait_for_budget(self.matrix.queues[name]):
          return 'budget_spent'
      # A run counts as in flight until its end (and usage) is logged, after
      # grading, so a budget check made while it's graded still counts it.
      counted = []
      try:
        async with contextlib.AsyncExitStack() as held:
          for name in sorted(cell.config.queues):  # A fixed order, so two runs can't deadlock.
            await held.enter_async_context(self._locks[name])
          await held.enter_async_context(self._slots)
          for name in cell.config.queues:
            self._running[name] += 1
            counted.append(name)
          self.log('start', **key, attempt=infra_attempts(cell, self.out) + 1)
          fingerprint_file(cell, self.out).parent.mkdir(parents=True, exist_ok=True)
          fingerprint_file(cell, self.out).write_text(json.dumps(current, indent=2) + '\n')
          started = self.now()
          code = await self.launch(run_args(cell, run_dir, self.matrix), log)
        record = _read_json(run_dir / 'record.json')
        if record is None:
          self.log('error', **key, exit_code=code, note='no run record; see the log')
          return 'config_error' if code == 2 else INFRA
        shares = usage_by_queue(cell.config, record)
        ended = {
          'outcome': record.get('outcome'), 'steps': record.get('steps'),
          'seconds': round(self.now() - started, 1),
          **shares[cell.config.queue], 'usage_by_queue': shares,
        }
        if cut_queue := self._cut_off(cell, record, shares):
          self.log('cutoff', **key, **ended, cut_queue=cut_queue, detail=record.get('outcome_detail'))
          _set_aside(run_dir, 'cutoff')
          continue
        if record.get('outcome') != 'infra_error':
          verdict = await self._grade(cell, run_dir, log, key, quiet=True)
          self.log('end', **key, **ended, **verdict)
          return DONE
        self.log('end', **key, **ended, detail=record.get('outcome_detail'))
        if _SPENDING_LIMIT.search(str(record.get('outcome_detail') or '')):
          _set_aside(run_dir, 'keylimit')
          return 'spending_limit'
        if network_failure(run_dir, record) and network_tries < NETWORK_RETRIES:
          network_tries += 1
          _set_aside(run_dir, 'network')
          await self._wait_for_network(cell, key)
          continue
      finally:
        for name in counted:
          self._running[name] -= 1
          self._finished[name] += 1
      if infra_attempts(cell, self.out) + 1 > self.matrix.infra_retries:
        return INFRA
      _set_aside(run_dir, 'infra')
      self.log('retry', **key, after_s=self.matrix.infra_delay_s)
      await self.sleep(self.matrix.infra_delay_s)

  async def _wait_for_network(self, cell: Cell, key: dict) -> None:
    """Wait until the config's API host resolves again, then a little longer."""
    host = api_host(cell.config)
    self.log('network_down', **key, host=host)
    waited = 0.0
    while not await self.network_up(host):
      await self.sleep(30.0)
      waited += 30.0
    await self.sleep(30.0)
    self.log('network_back', **key, host=host, waited_s=waited)

  async def _grade(self, cell: Cell, run_dir: Path, log: Path, key: dict, quiet: bool = False) -> dict:
    code = await self.launch(['grade', str(run_dir)], log)
    grade = _read_json(run_dir / 'grade.json') or {}
    verdict = {
      name: grade.get(name)
      for name in ('said_and_done', 'verified_success', 'false_completion', 'wrongly_blocked', 'unjustified_block')
      if name in grade
    }
    violations = (grade.get('checks') or {}).get('violations')
    if violations:
      verdict['violations'] = violations
    if code or not grade:
      verdict['grade_error'] = f'exit code {code}; see the log'
    if not quiet:
      self.log('graded', **key, **verdict)
    return verdict

  def shares(self, queue: Queue) -> list[tuple[float, dict]]:
    """(time, usage) for every finished run that drew on this queue."""
    found = []
    for event in self.events:
      if event.get('event') not in ('end', 'cutoff'):
        continue
      by_queue = event.get('usage_by_queue') or (
        {event.get('queue'): event} if event.get('queue') else {}
      )
      if queue.name in by_queue:
        found.append((event['time'], by_queue[queue.name]))
    return found

  def usage_today(self, queue: Queue) -> tuple[int, int, list[dict]]:
    today = _utc_day(self.now())
    shares = self.shares(queue)
    todays = [usage for when, usage in shares if _utc_day(when) == today]
    return (
      sum(usage.get('output_tokens') or 0 for usage in todays),
      sum(usage.get('requests') or 0 for usage in todays),
      [usage for _, usage in shares],
    )

  def _cut_off(self, cell: Cell, record: dict, shares: dict) -> str | None:
    """The queue whose daily budget the provider cut this run off at, if any."""
    errored = (
      record.get('outcome') == 'infra_error' or record.get('agent_errors') or record.get('stuck_turns')
      or (record.get('agent_info') or {}).get('retry_reasons')
    )
    if not errored:
      return None
    for name in cell.config.queues:
      queue = self.matrix.queues[name]
      if not (queue.cutoff_margin and queue.daily_output_tokens):
        continue
      tokens, _, _ = self.usage_today(queue)
      if tokens + ((shares.get(name) or {}).get('output_tokens') or 0) >= queue.daily_output_tokens - queue.cutoff_margin:
        return name
    return None

  def _cut_off_today(self, queue: Queue) -> bool:
    today = _utc_day(self.now())
    return any(
      event.get('event') == 'cutoff' and event.get('cut_queue') == queue.name and _utc_day(event['time']) == today
      for event in self.events
    )

  async def _wait_for_budget(self, queue: Queue) -> bool:
    """Wait until the queue's next run fits its budgets; return False if it never will.

    With runs in flight it waits for them and looks again, since their cost is
    still to come. A queue with a budget runs one cell first, to learn what a
    run costs. Past a daily budget it waits for the next UTC day; past its
    budget for the whole batch, with nothing in flight, it stops.
    """
    capped = queue.max_cost_usd is not None or queue.daily_output_tokens or queue.daily_requests
    while True:
      running = getattr(self, '_running', {}).get(queue.name, 0)
      tokens, requests, ends = self.usage_today(queue)
      if capped and not ends and running:
        await self._a_run_ends(queue)
        continue
      recent = ends[-5:]
      runs_ahead = 1 + running  # The runs in flight will spend too.
      if queue.max_cost_usd is not None:
        spent = sum(usage.get('cost_usd') or 0 for usage in ends)
        expect_cost = runs_ahead * max((usage.get('cost_usd') or 0 for usage in recent), default=0)
        if spent + expect_cost > queue.max_cost_usd:
          if running:
            await self._a_run_ends(queue)
            continue
          self.log('budget_spent', queue=queue.name, cost_usd=round(spent, 2), max_cost_usd=queue.max_cost_usd)
          return False
      # A queue that sets aside the run cut off at its budget doesn't hold back
      # a run's worth; once one is cut off, it's done for the day.
      expect_tokens = 0 if queue.cutoff_margin else runs_ahead * max((usage.get('output_tokens') or 0 for usage in recent), default=0)
      expect_requests = runs_ahead * max((usage.get('requests') or 0 for usage in recent), default=0)
      over = (
        (queue.cutoff_margin and self._cut_off_today(queue))
        or (queue.daily_output_tokens and tokens + expect_tokens > queue.daily_output_tokens)
        or (queue.daily_requests and requests + expect_requests > queue.daily_requests)
      )
      if not over:
        return True
      if running:
        await self._a_run_ends(queue)
        continue
      wait = _next_utc_day(self.now()) + 60 - self.now()
      self.log('budget_wait', queue=queue.name, seconds=round(wait), output_tokens_today=tokens, requests_today=requests)
      await self.sleep(wait)

  async def _a_run_ends(self, queue: Queue) -> None:
    """Return once one of the queue's runs in flight has ended (or none is in flight).

    Counts ends rather than watching the number in flight, which another worker
    can bring straight back up by starting its next run between two looks.
    """
    before = self._finished.get(queue.name, 0)
    while self._running.get(queue.name, 0) > 0 and self._finished.get(queue.name, 0) == before:
      await asyncio.sleep(0.2)

def _read_line(line: str) -> dict | None:
  try:
    return json.loads(line)
  except ValueError:
    return None


# One letter per seed in the status table.
SYMBOLS = {
  'success': 'S', 'false_completion': 'F', 'wrongly_blocked': 'W', 'unjustified_block': 'U',
  'other': 'x', INFRA: 'I', STALE: 's', GRADE_ERROR: 'g', 'pending': '.',
}


def cell_symbol(cell: Cell, out: Path) -> str:
  state = cell_state(cell, out)
  if state in (EMPTY, INCOMPLETE, UNGRADED):
    return SYMBOLS['pending']
  if state in (INFRA, STALE, GRADE_ERROR):
    return SYMBOLS[state]
  grade = _read_json(cell.run_dir(out) / 'grade.json') or {}
  for name, symbol in (('verified_success', 'S'), ('false_completion', 'F'), ('wrongly_blocked', 'W'), ('unjustified_block', 'U')):
    if grade.get(name):
      untruthful = grade.get('claims_truthful') is False and symbol == 'S'
      return symbol + ('?' if untruthful else '') + ('!' if (grade.get('checks') or {}).get('violations') else '')
  return SYMBOLS['other'] + ('!' if (grade.get('checks') or {}).get('violations') else '')


def status_table(cells: Sequence[Cell], out: Path) -> str:
  task_ids = list(dict.fromkeys(cell.task.id for cell in cells))
  config_names = list(dict.fromkeys(cell.config.name for cell in cells))
  by_key: dict[tuple[str, str], list[str]] = {}
  for cell in sorted(cells, key=lambda cell: cell.seed):
    by_key.setdefault((cell.task.id, cell.config.name), []).append(cell_symbol(cell, out))
  width = max(len(name) for name in task_ids) + 2
  columns = [max(len(name), 6) + 2 for name in config_names]
  lines = [' ' * width + ''.join(name.ljust(column) for name, column in zip(config_names, columns))]
  for task_id in task_ids:
    row = task_id.ljust(width)
    for name, column in zip(config_names, columns):
      row += ' '.join(by_key.get((task_id, name), ['-'])).ljust(column)
    lines.append(row)
  lines.append('')
  lines.append('S verified success, F false completion, W wrongly blocked, U unjustified block, '
               'x other (stalled, step cap, timeout), ? with a false claim, ! with a violation, I infrastructure error, '
               'g grader failed (grade again), s stale (older task version), . not run yet, - not eligible')
  return '\n'.join(lines)
