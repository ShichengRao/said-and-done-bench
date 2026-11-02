"""The batch runner, with a fake launcher and clock: no models, no containers."""

import asyncio
import dataclasses
import datetime
import json
from pathlib import Path

import pytest

from beambench import batch, tasks
from beambench.batch import Batch, Cell, Config, Matrix, Queue, plan

REPO = Path(__file__).resolve().parent.parent
HELLO, WRONGFIX = (tasks.load_task(REPO / 'tasks' / name) for name in ('hello', 'wrongfix-pr'))
DAY = datetime.datetime(2026, 10, 27, 23, 0, tzinfo=datetime.UTC).timestamp()


def matrix(**queues):
  queues = queues or {'a': {}, 'b': {}}
  configs = {
    'beam': Config('beam', 'neutral', 'a', model_config='beam-reflection'),
    'codex': Config('codex', 'codex', 'b'),
  }
  return Matrix(
    configs=configs, queues={name: Queue(name, **spec) for name, spec in queues.items()},
    seeds=(1, 2), tasks=(), infra_delay_s=300.0, outage_after=3, outage_pause_s=1800.0,
  )


class Fake:
  """Launches `run` and `grade` by writing what they would; outcomes per cell come from a script."""

  def __init__(self, script=None, tokens=0, run_exit=0, cost=0.0, worker_tokens=0, grade_seconds=0.0, infra_detail=None, run_seconds=0.01):
    self.grade_seconds, self.infra_detail, self.run_seconds = grade_seconds, infra_detail, run_seconds
    self.script = {key: list(value) for key, value in (script or {}).items()}
    self.tokens, self.run_exit = tokens, run_exit
    self.cost, self.worker_tokens = cost, worker_tokens
    self.active, self.max_active_on_a = 0, 0
    self.calls, self.running, self.overlap = [], {}, False
    self.now_value, self.slept = DAY, []
    self.harness = 'h1'
    self.grader_fails = False

  async def fingerprint(self, cell, matrix):
    return {'harness_hash': self.harness, 'agent': cell.config.agent}

  def now(self):
    return self.now_value

  async def sleep(self, seconds):
    self.slept.append(seconds)
    self.now_value += seconds

  async def launch(self, args, log):
    run_dir = Path(args[args.index('--run-dir') + 1] if args[0] == 'run' else args[1])
    task_id, config, seed = run_dir.parts[-3], run_dir.parts[-2], run_dir.name
    spec = HELLO if task_id == 'hello' else WRONGFIX
    self.calls.append((args[0], task_id, config, seed))
    if args[0] == 'grade':
      await asyncio.sleep(self.grade_seconds)  # Lets other runs start while this one is graded.
      record = json.loads((run_dir / 'record.json').read_text())
      if self.grader_fails:
        (run_dir / 'grade.json').write_text(json.dumps({
          'verified_success': None, 'false_completion': None, 'grader_hash': tasks.grader_hash(spec),
          'checks': {'passed': False, 'grader_error': 'the grader ran past 600 s'},
        }))
        return 0
      (run_dir / 'grade.json').write_text(json.dumps({
        'verified_success': record['outcome'] == 'complete', 'false_completion': False,
        'grader_hash': tasks.grader_hash(spec), 'checks': {'violations': []},
      }))
      return 0
    queue = 'b' if config in ('codex', 'brain') else 'a'
    self.overlap |= self.running.get(queue, 0) > 0
    self.running[queue] = self.running.get(queue, 0) + 1
    self.max_running = getattr(self, 'max_running', {})
    self.max_running[queue] = max(self.max_running.get(queue, 0), self.running[queue])
    uses_a = config in ('beam', 'brain')  # The brain's worker draws on queue a too.
    self.active += uses_a
    self.max_active_on_a = max(self.max_active_on_a, self.active)
    await asyncio.sleep(self.run_seconds)  # Lets the other queue's worker interleave.
    self.active -= uses_a
    self.running[queue] -= 1
    if self.run_exit:
      return self.run_exit
    outcomes = self.script.get((task_id, config, seed))
    outcome = outcomes.pop(0) if outcomes else 'complete'
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'record.json').write_text(json.dumps({
      'outcome': outcome, 'steps': 3, 'task': {'task_hash': tasks.task_hash(spec)},
      'outcome_detail': self.infra_detail if outcome == 'infra_error' else None,
      'usage_total': {'completion_tokens': self.tokens, 'requests': 4, 'cost_usd': self.cost},
      'worker': {'usage': {'completion_tokens': self.worker_tokens, 'requests': 2}} if config == 'brain' else None,
    }))
    return 1 if outcome == 'infra_error' else 0


def cells(m, task_specs=(HELLO, WRONGFIX)):
  return [Cell(spec, config, seed) for seed in m.seeds for spec in task_specs for config in m.configs.values()]


def run_batch(tmp_path, m, fake, cell_list=None, **kwargs):
  runner = Batch(
    m, tmp_path, cell_list or cells(m), launch=fake.launch, now=fake.now, sleep=fake.sleep,
    fingerprint=fake.fingerprint, **kwargs,
  )
  asyncio.run(runner.run())
  return runner


def events(tmp_path, kind=None):
  lines = [json.loads(line) for line in (tmp_path / 'batch.jsonl').read_text().splitlines()]
  return [line for line in lines if kind is None or line['event'] == kind]


def test_the_matrix_plan_is_seed_major_and_respects_tracks():
  m = batch.load_matrix()
  planned = plan(m)
  assert len(planned) == 444  # 15 configs x 15 tasks x 2 seeds, minus probe-creds on 3 native configs.
  assert [cell.seed for cell in planned] == sorted(cell.seed for cell in planned)
  assert not [cell for cell in planned if cell.task.id == 'probe-creds' and cell.config.track == 'native']
  assert 'hello' not in {cell.task.id for cell in planned}
  assert {cell.config.queue for cell in planned if cell.config.name.startswith('beam')} == {'reflection'}


def test_runs_every_cell_once_then_resumes_without_rerunning(tmp_path):
  m, fake = matrix(), Fake()
  run_batch(tmp_path, m, fake)
  runs = [call for call in fake.calls if call[0] == 'run']
  assert len(runs) == 8 and len(fake.calls) == 16
  assert not fake.overlap  # One run at a time within a queue.
  # Seed-major within each queue.
  assert [call[3] for call in runs if call[2] == 'beam'] == ['seed-1', 'seed-1', 'seed-2', 'seed-2']
  assert all(event['verified_success'] for event in events(tmp_path, 'end'))
  again = Fake()
  run_batch(tmp_path, m, again)
  assert again.calls == []
  assert 'S' in batch.status_table(cells(m), tmp_path)


def test_an_infrastructure_error_is_retried_once_after_a_delay(tmp_path):
  m = matrix()
  fake = Fake(script={('hello', 'beam', 'seed-1'): ['infra_error', 'complete']})
  run_batch(tmp_path, m, fake)
  cell_dir = tmp_path / 'hello' / 'beam'
  assert (cell_dir / 'seed-1.infra-1' / 'record.json').exists()
  assert json.loads((cell_dir / 'seed-1' / 'record.json').read_text())['outcome'] == 'complete'
  assert 300.0 in fake.slept
  assert [event['attempt'] for event in events(tmp_path, 'start') if event['task'] == 'hello'
          and event['config'] == 'beam' and event['seed'] == 1] == [1, 2]


def test_a_second_infrastructure_error_is_final_and_not_retried_on_resume(tmp_path):
  m = matrix()
  fake = Fake(script={('hello', 'beam', 'seed-1'): ['infra_error', 'infra_error']})
  run_batch(tmp_path, m, fake)
  state = batch.cell_state(Cell(HELLO, m.configs['beam'], 1), tmp_path)
  assert state == batch.INFRA
  again = Fake()
  run_batch(tmp_path, m, again)
  assert again.calls == [] and again.slept == []
  assert 'I' in batch.status_table(cells(m), tmp_path)


def test_a_run_cut_off_is_set_aside_and_rerun_and_an_ungraded_one_is_graded(tmp_path):
  m = matrix()
  cut_off = tmp_path / 'hello' / 'beam' / 'seed-1'
  cut_off.mkdir(parents=True)
  (cut_off / 'workspace').mkdir()
  fake = Fake()
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], 1)])
  assert (tmp_path / 'hello' / 'beam' / 'seed-1.incomplete-1' / 'workspace').exists()
  (tmp_path / 'hello' / 'beam' / 'seed-1' / 'grade.json').unlink()
  regrade = Fake()
  run_batch(tmp_path, m, regrade, cell_list=[Cell(HELLO, m.configs['beam'], 1)])
  assert regrade.calls == [('grade', 'hello', 'beam', 'seed-1')]


def test_a_run_on_an_older_task_version_is_left_unless_asked(tmp_path):
  m = matrix()
  cell = Cell(HELLO, m.configs['beam'], 1)
  run_dir = cell.run_dir(tmp_path)
  run_dir.mkdir(parents=True)
  (run_dir / 'record.json').write_text(json.dumps({'outcome': 'complete', 'task': {'task_hash': 'old'}}))
  fake = Fake()
  run_batch(tmp_path, m, fake, cell_list=[cell])
  assert fake.calls == [] and events(tmp_path, 'stale')
  run_batch(tmp_path, m, fake, cell_list=[cell], rerun_stale=True)
  assert (run_dir.parent / 'seed-1.stale-1' / 'record.json').exists()
  assert [call[0] for call in fake.calls] == ['run', 'grade']


def test_a_queue_waits_for_the_next_utc_day_when_its_budget_would_run_out(tmp_path):
  m = matrix(a={'daily_output_tokens': 100}, b={})
  fake = Fake(tokens=60)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in (1, 2, 3)])
  waits = events(tmp_path, 'budget_wait')
  assert len(waits) == 2  # 60 fits a day, 120 doesn't.
  assert waits[0]['seconds'] == 3600 + 60  # 23:00 UTC to just after midnight.
  ends = events(tmp_path, 'end')
  days = {datetime.datetime.fromtimestamp(event['time'], datetime.UTC).date() for event in ends}
  assert len(days) == 3


def test_a_config_that_cannot_start_stops_its_queue_but_not_the_others(tmp_path):
  m = matrix()

  class MissingCredential(Fake):
    async def launch(self, args, log):
      if args[0] == 'run' and '/codex/' in args[args.index('--run-dir') + 1]:
        self.calls.append(('run', 'codex-failed'))
        return 2  # argparse's error: e.g. no sign-in.
      return await super().launch(args, log)

  fake = MissingCredential()
  run_batch(tmp_path, m, fake)
  assert fake.calls.count(('run', 'codex-failed')) == 1
  assert len([call for call in fake.calls if call[0] == 'run' and call[2:3] == ('beam',)]) == 4
  assert events(tmp_path, 'queue_stopped')[0]['queue'] == 'b'


def test_repeated_infrastructure_errors_pause_the_queue(tmp_path):
  m = matrix()
  fake = Fake(script={
    (task.id, 'beam', f'seed-{seed}'): ['infra_error', 'infra_error'] for task in (HELLO, WRONGFIX) for seed in (1, 2)
  })
  run_batch(tmp_path, m, fake, cell_list=[cell for cell in cells(m) if cell.config.name == 'beam'])
  assert events(tmp_path, 'queue_paused') and 1800.0 in fake.slept


def test_a_run_on_an_older_harness_or_config_is_stale(tmp_path):
  m = matrix()
  cell = Cell(HELLO, m.configs['beam'], 1)
  run_batch(tmp_path, m, Fake(), cell_list=[cell])
  changed = Fake()
  changed.harness = 'h2'
  run_batch(tmp_path, m, changed, cell_list=[cell])
  assert changed.calls == [] and events(tmp_path, 'stale')[-1]['changed'] == ['harness_hash']
  run_batch(tmp_path, m, changed, cell_list=[cell], rerun_stale=True)
  assert [call[0] for call in changed.calls] == ['run', 'grade']
  assert (cell.run_dir(tmp_path).parent / 'seed-1.stale-1.fingerprint.json').exists()
  assert json.loads(batch.fingerprint_file(cell, tmp_path).read_text())['harness_hash'] == 'h2'


def test_a_grader_failure_is_not_a_result_and_is_graded_again(tmp_path):
  m = matrix()
  cell = Cell(HELLO, m.configs['beam'], 1)
  failing = Fake()
  failing.grader_fails = True
  run_batch(tmp_path, m, failing, cell_list=[cell])
  assert batch.cell_state(cell, tmp_path) == batch.GRADE_ERROR
  assert 'g' in batch.status_table([cell], tmp_path) and 'F' not in batch.status_table([cell], tmp_path).splitlines()[1]
  again = Fake()
  run_batch(tmp_path, m, again, cell_list=[cell])
  assert again.calls == [('grade', 'hello', 'beam', 'seed-1')]
  assert batch.cell_state(cell, tmp_path) == batch.DONE


def brain_matrix(**queues):
  m = matrix(**queues)
  configs = {
    'beam': m.configs['beam'],
    'brain': Config('brain', 'claude', 'b', claude_auth='api', worker='beam-reflection', also_uses=('a',)),
  }
  return dataclasses.replace(m, configs=configs)


def test_a_brain_holds_its_workers_queue_so_it_never_overlaps_a_beam_run(tmp_path):
  m = brain_matrix()
  fake = Fake()
  run_batch(tmp_path, m, fake)
  assert len([call for call in fake.calls if call[0] == 'run']) == 8
  assert fake.max_active_on_a == 1
  assert [call for call in fake.calls if call[0] == 'run' and call[2] == 'brain'][0][1:] == ('hello', 'brain', 'seed-1')
  assert '--worker' in batch.run_args(Cell(HELLO, m.configs['brain'], 1), tmp_path, m)


def test_a_workers_tokens_count_against_its_queues_daily_budget(tmp_path):
  m = brain_matrix(a={'daily_output_tokens': 100}, b={})
  fake = Fake(worker_tokens=60)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['brain'], seed) for seed in (1, 2)])
  end = events(tmp_path, 'end')[0]
  assert end['usage_by_queue'] == {
    'b': {'output_tokens': 0, 'requests': 4, 'cost_usd': 0.0},
    'a': {'output_tokens': 60, 'requests': 2, 'cost_usd': 0.0},
  }
  assert events(tmp_path, 'budget_wait')[0]['queue'] == 'a'


def test_a_queue_stops_when_its_dollar_budget_is_spent(tmp_path):
  m = matrix(a={'max_cost_usd': 5.0}, b={})
  fake = Fake(cost=2.0)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in (1, 2, 3)])
  assert len([call for call in fake.calls if call[0] == 'run']) == 2  # $4 spent; a third would pass $5.
  assert events(tmp_path, 'budget_spent') and events(tmp_path, 'queue_stopped')


def test_a_queue_runs_as_many_cells_at_once_as_its_parallel_setting(tmp_path):
  m = matrix(a={}, b={'parallel': 2})
  fake = Fake()
  codex_cells = [Cell(task, m.configs['codex'], seed) for seed in (1, 2) for task in (HELLO, WRONGFIX)]
  run_batch(tmp_path, m, fake, cell_list=codex_cells)
  assert fake.max_running['b'] == 2 and len([call for call in fake.calls if call[0] == 'run']) == 4


def test_a_brain_never_overlaps_beam_even_when_its_own_queue_has_room(tmp_path):
  m = brain_matrix(a={}, b={'parallel': 3})
  fake = Fake()
  run_batch(tmp_path, m, fake)
  assert fake.max_active_on_a == 1
  assert len([call for call in fake.calls if call[0] == 'run']) == 8


def test_parallel_runs_dont_overshoot_a_dollar_budget(tmp_path):
  m = matrix(a={'max_cost_usd': 5.0, 'parallel': 3}, b={})
  fake = Fake(cost=2.0)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in range(1, 7)])
  spent = sum(event.get('cost_usd') or 0 for event in events(tmp_path, 'end'))
  assert spent <= 5.0 and events(tmp_path, 'queue_stopped')


def test_a_run_being_graded_still_counts_against_the_budget(tmp_path):
  m = matrix(a={'max_cost_usd': 5.0, 'parallel': 3}, b={})
  fake = Fake(cost=2.0, grade_seconds=0.5)  # Longer than a waiting run's 0.2 s poll.
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in range(1, 7)])
  runs = [call for call in fake.calls if call[0] == 'run']
  assert len(runs) == 2  # The first is the warm-up; nothing starts while it's graded.
  assert sum(event.get('cost_usd') or 0 for event in events(tmp_path, 'end')) <= 5.0


def test_a_queue_with_a_cutoff_runs_to_its_budget_and_sets_aside_the_run_cut_off(tmp_path):
  m = matrix(a={'daily_output_tokens': 100, 'cutoff_margin': 30}, b={})
  fake = Fake(tokens=40, script={('hello', 'beam', 'seed-3'): ['infra_error', 'complete']})
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in (1, 2, 3, 4)])
  cell_dir = tmp_path / 'hello' / 'beam'
  # 80 tokens used: a third run starts (without a cutoff it would wait), errors, and is set aside.
  assert (cell_dir / 'seed-3.cutoff-1' / 'record.json').exists()
  assert not list(cell_dir.glob('seed-3.infra-*'))
  assert json.loads((cell_dir / 'seed-3' / 'record.json').read_text())['outcome'] == 'complete'
  cutoffs = events(tmp_path, 'cutoff')
  assert len(cutoffs) == 1 and cutoffs[0]['cut_queue'] == 'a' and cutoffs[0]['seed'] == 3
  assert len(events(tmp_path, 'budget_wait')) == 1 and 300.0 not in fake.slept
  reran = [event for event in events(tmp_path, 'end') if event['seed'] == 3]
  assert len(reran) == 1 and reran[0]['time'] > cutoffs[0]['time'] + 3600  # The next UTC day.
  assert {event['seed'] for event in events(tmp_path, 'end')} == {1, 2, 3, 4}


def test_an_error_well_short_of_the_budget_is_an_ordinary_infra_error(tmp_path):
  m = matrix(a={'daily_output_tokens': 100, 'cutoff_margin': 30}, b={})
  fake = Fake(tokens=40, script={('hello', 'beam', 'seed-1'): ['infra_error', 'complete']})
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], 1)])
  assert (tmp_path / 'hello' / 'beam' / 'seed-1.infra-1').exists()
  assert not events(tmp_path, 'cutoff') and 300.0 in fake.slept


def test_a_spending_limit_stops_the_queue_without_using_a_retry(tmp_path):
  m = matrix()
  detail = 'ProviderError: HTTP 403 from https://openrouter.ai/api/v1: Key limit exceeded (weekly limit).'
  fake = Fake(script={('hello', 'beam', 'seed-1'): ['infra_error']}, infra_detail=detail)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in (1, 2)])
  cell_dir = tmp_path / 'hello' / 'beam'
  assert (cell_dir / 'seed-1.keylimit-1').exists() and not list(cell_dir.glob('seed-1.infra-*'))
  assert 300.0 not in fake.slept and len([call for call in fake.calls if call[0] == 'run']) == 1
  stopped = events(tmp_path, 'queue_stopped')
  assert len(stopped) == 1 and 'spending limit' in stopped[0]['reason']
  assert batch.cell_state(Cell(HELLO, m.configs['beam'], 1), tmp_path) == batch.EMPTY  # Rerun when resumed.


def test_a_worker_on_the_brains_own_queue_adds_to_it():
  brain = Config('beam-brain', 'neutral', 'a', model_config='beam-reflection', worker='beam-reflection')
  record = {'usage_total': {'completion_tokens': 30, 'requests': 3}, 'worker': {'usage': {'completion_tokens': 70, 'requests': 7}}}
  assert batch.usage_by_queue(brain, record) == {'a': {'output_tokens': 100, 'requests': 10, 'cost_usd': 0.0}}
  opus = Config('opus-brain', 'claude', 'b', worker='beam-reflection', also_uses=('a',))
  assert batch.usage_by_queue(opus, record) == {
    'b': {'output_tokens': 30, 'requests': 3, 'cost_usd': 0.0}, 'a': {'output_tokens': 70, 'requests': 7, 'cost_usd': 0.0},
  }


def test_workers_waiting_out_the_warm_up_all_start_after_it(tmp_path):
  m = matrix(a={'max_cost_usd': 100.0, 'parallel': 3}, b={})
  fake = Fake(cost=1.0, run_seconds=0.5)
  run_batch(tmp_path, m, fake, cell_list=[Cell(HELLO, m.configs['beam'], seed) for seed in range(1, 8)])
  assert fake.max_running['a'] == 3  # Not one at a time after the warm-up.


def test_a_network_drop_isnt_an_attempt_and_the_cell_runs_again_when_it_is_back(tmp_path):
  m = matrix()
  detail = 'ProviderError: the model API failed 6 times; last: ConnectError: [Errno 8] nodename nor servname provided, or not known'
  fake = Fake(script={('hello', 'beam', 'seed-1'): ['infra_error', 'complete']}, infra_detail=detail)
  checks = []

  async def network_up(host):
    checks.append(host)
    return len(checks) > 2  # Down for two checks, then back.

  runner = Batch(m, tmp_path, [Cell(HELLO, m.configs['beam'], 1)], launch=fake.launch, now=fake.now, sleep=fake.sleep,
                 fingerprint=fake.fingerprint, network_up=network_up)
  asyncio.run(runner.run())
  cell_dir = tmp_path / 'hello' / 'beam'
  assert (cell_dir / 'seed-1.network-1').exists() and not list(cell_dir.glob('seed-1.infra-*'))
  assert json.loads((cell_dir / 'seed-1' / 'record.json').read_text())['outcome'] == 'complete'
  assert 300.0 not in fake.slept and checks[0] == 'api.reflection.ai'
  assert [e['event'] for e in events(tmp_path) if e['event'].startswith('network')] == ['network_down', 'network_back']
  assert [e['attempt'] for e in events(tmp_path, 'start')] == [1, 1]


def test_a_v4_scaffold_config_passes_its_version_and_v3_cells_keep_their_args(tmp_path):
  m = matrix()
  v3 = Config('v3', 'neutral', 'a', model_config='beam-reflection', reviewer=True, guard=True, verifier=True)
  v4 = dataclasses.replace(v3, name='v4', scaffold_version=4)
  assert '--scaffold-version' not in batch.run_args(Cell(HELLO, v3, 1), tmp_path, m)
  args = batch.run_args(Cell(HELLO, v4, 1), tmp_path, m)
  assert args[args.index('--scaffold-version') + 1] == '4'


def test_a_family_runs_only_when_named_and_its_task_ids_work():
  m = batch.load_matrix()
  assert not [cell for cell in plan(m) if batch.family_of(cell.task)]  # The 15 tasks alone by default.
  family = batch.FAMILIES['no-valid-option']
  assert len(family.task_ids()) == 8 and '_shared' not in family.task_ids()
  beam = ['beam-neutral', 'beam-mirror', 'beam-neutral-scaffold-v4']
  planned = plan(m, only_tasks=['no-valid-option'], only_configs=beam, seeds=[1, 2])
  assert len(planned) == 48 and {batch.family_of(cell.task) for cell in planned} == {family}
  assert [cell.seed for cell in planned] == sorted(cell.seed for cell in planned)
  one = plan(m, only_tasks=['nv-drone-landing', 'wrongfix-pr'], only_configs=['beam-neutral'], seeds=[1])
  assert [cell.task.id for cell in one] == ['nv-drone-landing', 'wrongfix-pr']
  assert batch.family_of(one[0].task) == family and batch.family_of(one[1].task) is None
  try:
    plan(m, only_tasks=['no-such-task'])
  except ValueError as error:
    assert 'no-such-task' in str(error)
  else:
    raise AssertionError('an unknown task should fail')


def test_a_matrix_can_extend_another_and_give_a_config_its_own_queue(tmp_path):
  (tmp_path / 'base.toml').write_text(
    'seeds = [1, 2]\n[batch]\ninfra_retries = 2\n[queues.a]\nmax_cost_usd = 50.0\nparallel = 3\n'
    '[configs.x]\nagent = "neutral"\nmodel_config = "beam-reflection"\nqueue = "a"\nlabel = "X"\nreviewer = true\n')
  (tmp_path / 'study.toml').write_text(
    'extends = "base.toml"\nseeds = [3]\ntasks = ["no-valid-option"]\n[batch]\ninfra_delay_s = 60.0\n'
    '[queues.own]\nmax_cost_usd = 5.0\n[configs.x]\nqueue = "own"\n')
  base, study = batch.load_matrix(tmp_path / 'base.toml'), batch.load_matrix(tmp_path / 'study.toml')
  assert study.configs['x'] == dataclasses.replace(base.configs['x'], queue='own')
  assert study.queues['own'].max_cost_usd == 5.0 and study.queues['a'] == base.queues['a']
  assert study.seeds == (3,) and study.tasks == ('no-valid-option',)
  assert study.infra_retries == 2 and study.infra_delay_s == 60.0


def test_the_no_valid_option_study_runs_the_matrix_configs_on_queues_of_its_own():
  main = batch.load_matrix()
  study = batch.load_matrix(REPO / 'experiments' / 'no-valid-option.toml')
  for name, config in main.configs.items():  # Kimi K3: the endpoint tag its main column pinned is gone.
    changed = {'queue': config.queue} | ({'model_config': 'kimi-k3'} if name == 'kimi-k3' else {})
    assert dataclasses.replace(study.configs[name], **changed) == config, name
  assert study.configs['kimi-k3'].model_config == 'kimi-k3-moonshot'
  beam = [name for name in study.configs if name.startswith('beam')]
  assert {study.configs[name].queue for name in beam} == {'reflection'}
  peers = ['claude-opus-5-5', 'gemini-4-argon', 'glm-5-2', 'deepseek-v4-1-flash', 'nemotron-3-ultra', 'inkling',
           'qwen3-8-open', 'kimi-k3', 'deepseek-v3', 'gpt-6-astra']
  assert all(study.configs[name].queue.startswith('nv-') for name in peers)
  openrouter = {study.configs[name].queue for name in peers if name not in ('claude-opus-5-5', 'glm-5-2', 'gpt-6-astra')}
  assert sum(study.queues[queue].max_cost_usd for queue in openrouter) <= 30.0 - 0.84  # Less Kimi's uncounted run.
  assert study.queues['nv-anthropic'].max_cost_usd <= 15.0
  cells = plan(study, only_configs=peers)
  assert len(cells) == 160 and all(batch.family_of(cell.task) for cell in cells)


def test_parts_run_in_order_in_one_batch():
  import importlib.util
  spec = importlib.util.spec_from_file_location('batch_in_order', REPO / 'scripts' / 'batch_in_order.py')
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  beam = 'configs=beam-neutral,beam-mirror,beam-neutral-scaffold-v4'
  parts = [module.parse_part(['tasks=no-valid-option', beam, 'seeds=1,2']), module.parse_part([beam, 'seeds=3,4']),
           module.parse_part(['tasks=nv-drone-landing', beam, 'seeds=1'])]
  cells = module.plan_parts(batch.load_matrix(), parts)
  assert len(cells) == 48 + 88  # Seeds 3-4: 3 configs x 15 tasks x 2, minus probe-creds in Mirror; the last part repeats.
  assert all(batch.family_of(cell.task) for cell in cells[:48]) and not any(batch.family_of(cell.task) for cell in cells[48:])
  assert {cell.seed for cell in cells[48:]} == {3, 4}


def test_a_part_can_take_a_held_out_round():
  import importlib.util
  spec = importlib.util.spec_from_file_location('batch_in_order', REPO / 'scripts' / 'batch_in_order.py')
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  parts = [module.parse_part(['dir=heldout3', 'configs=beam-neutral,beam-neutral-scaffold-v4', 'seeds=1,2,3']),
           module.parse_part(['configs=beam-neutral', 'seeds=3'])]
  cells = module.plan_parts(batch.load_matrix(), parts)
  assert len(cells) == 8 * 2 * 3 + 15
  assert {cell.task.path.parent.name for cell in cells[:48]} == {'heldout3'}
  assert {cell.task.path.parent.name for cell in cells[48:]} == {'tasks'}
  assert [cell.seed for cell in cells[:48]] == sorted(cell.seed for cell in cells[:48])  # Seed-major.
  # Under a matrix whose default tasks are the scenarios, a folder still means that folder's tasks.
  study = batch.load_matrix(REPO / 'experiments' / 'no-valid-option.toml')
  cells = module.plan_parts(study, [module.parse_part(['dir=heldout3', 'configs=beam-neutral', 'seeds=1']),
                                    module.parse_part(['dir=tasks', 'configs=beam-neutral', 'seeds=3']),
                                    module.parse_part(['tasks=no-valid-option', 'configs=opus-brain-beam-worker', 'seeds=1'])])
  assert [cell.task.path.parent.name for cell in cells] == ['heldout3'] * 8 + ['tasks'] * 15 + ['scenarios'] * 8
  for bad in ('dir=no-such-folder', 'dir=heldout,heldout2'):
    with pytest.raises(SystemExit):
      module.plan_parts(batch.load_matrix(), [module.parse_part([bad, 'configs=beam-neutral'])])


def test_the_held_out_walls_are_their_originals_but_for_id_family_and_tracks():
  from beambench.tasks import load_task, task_hash
  originals = {'hw-email-migrate': 'heldout/ho-email-migrate', 'hw-q3-revenue': 'heldout2/h2-q3-revenue',
               'hw-timesheet-export': 'heldout2/h2-timesheet-export', 'hw-northwind-sig': 'heldout3/h3-northwind-sig',
               'hw-sync-window': 'heldout3/h3-sync-window'}
  family = batch.FAMILIES['heldout-walls']
  assert family.in_score and not family.section and family.task_ids() == sorted(originals)
  for copy_id, original in originals.items():
    copy, source = REPO / 'walls' / copy_id, REPO / original
    files = lambda root: sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    assert files(copy) == files(source)
    for name in files(source):
      if name != 'task.toml':
        assert (copy / name).read_bytes() == (source / name).read_bytes(), (copy_id, name)
    spec, base = load_task(copy), load_task(source)
    assert (spec.id, spec.family, spec.tracks, spec.expected_status) == (copy_id, 'heldout-wall', ('neutral', 'native'), 'blocked')
    assert (base.tracks, base.goal, base.claims) == (('neutral',), spec.goal, spec.claims) and task_hash(spec) != task_hash(base)
