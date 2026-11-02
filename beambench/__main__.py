"""Benchmark commands: `run` a task with an agent, `grade` a run, run the whole matrix with `batch`,
do a task yourself with `human` (and `shell`), or `login` once per credential."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

from beambench import batch as batch_module
from beambench import claude_code, codex, costs, grading, human, mirror, neutral, neutral_brain, report, scaffold, secrets, tasks
from beambench import sidecars as sidecar_module
from beambench import scrub
from beambench.container import TELEMETRY_DIR, Container
from beambench.outcomes import Outcome, RunLimits
from beambench.runner import AgentSession, Task, approve_all, approve_matching, deny_all, run_task


AGENTS = {'mirror': mirror, 'claude': claude_code, 'codex': codex, 'neutral': neutral, 'human': human}
# Credentials passed to the container by environment variable. Codex signs in
# with a file instead (see codex.py), and the neutral harness keeps its
# provider's key outside the container (see models.toml).
CREDENTIAL_ENV = {'mirror': mirror.API_KEY_ENV, 'claude': claude_code.TOKEN_ENV}
# What `login` can store: an agent credential or a model provider's API key.
LOGIN_KEYS = {
  'claude': claude_code.TOKEN_ENV,
  'anthropic': claude_code.API_KEY_ENV,
  'reflection': mirror.API_KEY_ENV,
  'openrouter': 'OPENROUTER_API_KEY',
  'huggingface': 'HF_TOKEN',
}
# The task environment (neutral track, setup, grading) and each native agent's
# image, which adds only that agent's CLI (see container/Dockerfile).
TASK_IMAGE = 'beambench-task:dev'
AGENT_IMAGES = {
  'mirror': 'beambench-mirror:dev',
  'claude': 'beambench-claude:dev',
  'codex': 'beambench-codex:dev',
  'neutral': TASK_IMAGE,
  'human': TASK_IMAGE,
}


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(prog='python -m beambench', description=__doc__)
  commands = parser.add_subparsers(dest='command', required=True)

  run = commands.add_parser('run', help='run one task with one agent and record the outcome')
  run.add_argument('--agent', choices=tuple(name for name in AGENTS if name != 'human'), required=True)
  run.add_argument('--task', type=Path, required=True, help='a task folder, e.g. tasks/wrongfix-pr')
  run.add_argument('--run-dir', type=Path, required=True, help='a new folder for this run')
  run.add_argument(
    '--docker-image',
    help="the agent's image; each run gets a fresh container from it (default: the agent's, "
    'see container/Dockerfile)',
  )
  run.add_argument(
    '--task-image', default=TASK_IMAGE, help='the image that builds the workspace and grades the run',
  )
  run.add_argument(
    '--model-config', choices=tuple(neutral.load_models()),
    help=f'neutral only: which entry in {neutral.MODELS_FILE.name} to run',
  )
  run.add_argument(
    '--command-timeout', type=float,
    help="neutral only: seconds before a command is stopped (default: the task's)",
  )
  run.add_argument(
    '--model',
    help=f'claude and codex; defaults: {claude_code.DEFAULT_MODEL}, {codex.DEFAULT_MODEL}',
  )
  run.add_argument('--effort', default='max', help='claude and codex; Mirror always runs at max')
  run.add_argument(
    '--claude-auth', choices=('api', 'subscription'), default='api',
    help='claude only: an API key (billed by the token, cost recorded) or a subscription token',
  )
  run.add_argument(
    '--worker', choices=tuple(neutral.load_models()),
    help=f'claude or neutral: run the agent as a brain that reads and delegates to this {neutral.MODELS_FILE.name} '
    'model, which does the edits and commands',
  )
  run.add_argument(
    '--kickoff-note', default='', help='an extra paragraph at the end of the first prompt (for experiments)',
  )
  run.add_argument(
    '--system-note', default='', help='neutral only: a paragraph added to the system prompt (a mitigation)',
  )
  run.add_argument(
    '--review-submit', action='store_true',
    help='hold the first "complete" submission for one review turn before recording it (a mitigation)',
  )
  run.add_argument(
    '--reviewer', action='store_true',
    help='neutral only: an independent call to the same model reviews each "complete" before it is accepted '
    'and sends problems back to the agent (scaffold.py)',
  )
  run.add_argument(
    '--guard', action='store_true',
    help='neutral only: an independent call to the same model checks risky commands against the task\'s rules '
    'before they run (scaffold.py)',
  )
  run.add_argument(
    '--submit-tool', action='store_true', help='neutral only: submit with a `submit` tool next to bash',
  )
  run.add_argument(
    '--verifier', action='store_true',
    help='with --reviewer: before the first review, a fresh agent exercises a copy of the work in a container '
    'of its own, and the reviewer reads its findings (scaffold.py)',
  )
  run.add_argument(
    '--scaffold-options', help='JSON, for stress tests of v5: {"off": [parts switched off], "prompts": '
    '"a TOML file of reworded prompts"} (scaffold.py)',
  )
  run.add_argument(
    '--scaffold-version', type=int, default=scaffold.VERSION, choices=scaffold.VERSIONS,
    help='the scaffold\'s version: 4 adds a progress check during the run and v4\'s verifier, reviewer, and '
    'guard (scaffold.py)',
  )
  approval = run.add_mutually_exclusive_group()
  approval.add_argument('--approve-only', metavar='REGEX', help='mirror only: approve only tool calls whose JSON matches REGEX')
  approval.add_argument('--deny-all', action='store_true', help='mirror only: deny every tool call')
  limits = RunLimits()
  run.add_argument('--max-steps', type=int, default=limits.max_steps)
  run.add_argument('--stuck-turn', type=float, default=limits.stuck_turn_s, help='cancel a turn after this many seconds with no activity')
  run.add_argument('--run-deadline', type=float, default=limits.run_deadline_s, help='seconds')

  login = commands.add_parser(
    'login',
    help=f'store an agent credential for later runs, in {secrets.SECRETS_FILE} '
    f'(Codex: {codex.AUTH_DIR})',
  )
  login.add_argument('agent', choices=(*LOGIN_KEYS, 'codex'))
  login.add_argument(
    '--paste-only', action='store_true',
    help="claude only: paste an existing token instead of running `claude setup-token`",
  )
  login.add_argument(
    '--docker-image', default=AGENT_IMAGES['codex'], help='codex only: the image whose Codex signs in'
  )

  grade = commands.add_parser('grade', help="run a finished run's hidden checks and write grade.json")
  grade.add_argument('run_dir', type=Path)
  grade.add_argument('--docker-image', help='default: the image the run used')

  batch = commands.add_parser(
    'batch', help='run every config on every task, seed by seed (matrix.toml); safe to stop and resume',
  )
  batch.add_argument('--out', type=Path, required=True, help='the batch folder, e.g. runs/main')
  batch.add_argument('--matrix', type=Path, default=batch_module.MATRIX_FILE)
  batch.add_argument('--tasks', help="comma-separated task ids (default: the matrix's)")
  batch.add_argument('--configs', help='comma-separated config names (default: all)')
  batch.add_argument('--seeds', help="comma-separated seeds (default: the matrix's)")
  batch.add_argument('--max-parallel', type=int, help='runs at once across queues (default: one per queue)')
  batch.add_argument('--rerun-stale', action='store_true', help='rerun cells recorded on an older task version')
  batch.add_argument('--dry-run', action='store_true', help='show what would run, per queue, and exit')
  batch.add_argument('--status', action='store_true', help='print a table of results so far and exit')
  batch.add_argument(
    '--report', action='store_true', help='print success, false completion, time, and cost per config, and exit',
  )

  results = commands.add_parser(
    'report', help="a batch's results: the Said & Done score per config, tables, and charts",
  )
  results.add_argument('--out', type=Path, required=True, help='the batch folder, e.g. runs/main')
  results.add_argument('--matrix', type=Path, default=batch_module.MATRIX_FILE)
  results.add_argument('--to', type=Path, help='default: <out>/report')
  results.add_argument('--tasks', help="comma-separated task ids (default: the matrix's)")
  results.add_argument('--configs', help='comma-separated config names (default: all)')
  results.add_argument('--omit', help='comma-separated config names left out of the shown results, each with a note '
                       '(docs/report/omitted.toml)')

  person = commands.add_parser(
    'human', help='do a task yourself, as the human baseline: same setup, logged shell, graded at submit',
  )
  person.add_argument('--task', type=Path, required=True, help='a task folder, e.g. tasks/flaky-order')
  person.add_argument('--run-dir', type=Path, help='default: runs/human/<task>-<date-time>')
  person.add_argument('--hours', type=float, default=8.0, help='the run ends after this long')

  shell = commands.add_parser('shell', help="open the logged shell in a human run's container")
  shell.add_argument('run_dir', type=Path)

  args = parser.parse_args(argv)
  if args.command == 'report':
    names = lambda value: [item.strip() for item in value.split(',') if item.strip()] if value else []
    matrix = batch_module.load_matrix(args.matrix)
    cells = batch_module.plan(matrix, only_tasks=names(args.tasks), only_configs=names(args.configs))
    shown = [matrix.configs[name] for name in names(args.configs)] if args.configs else list(matrix.configs.values())
    omitted = [matrix.configs[name] for name in names(args.omit)]
    omitted_cells = batch_module.plan(matrix, only_tasks=names(args.tasks), only_configs=names(args.omit)) if omitted else []
    to = report.write_report(cells, args.out.resolve(), args.to.resolve() if args.to else None, configs=shown,
                             omitted=omitted, omitted_cells=omitted_cells)
    print((to / 'results.md').read_text())
    print(f'Written to {to}')
    return 0
  if args.command == 'human':
    return _human(person, args)
  if args.command == 'shell':
    return _shell(shell, args)
  if args.command == 'batch':
    return _batch(batch, args)
  if args.command == 'login':
    return _login(args)
  if args.command == 'grade':
    verdict = asyncio.run(grading.grade_run(args.run_dir.resolve(), args.docker_image))
    print(json.dumps({key: value for key, value in verdict.items() if key != 'checks'}, indent=2))
    return 0
  return _run(run, args, limits)


async def _cancel_on_sigterm(coroutine):
  """Run coroutine, cancelling it on SIGTERM as on Ctrl-C, so its cleanup still runs
  (a killed run otherwise leaves its agent container and sidecars behind)."""
  task = asyncio.current_task()
  asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
  return await coroutine


def _human(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
  spec = tasks.load_task(args.task)
  run_dir = (args.run_dir or Path('runs') / 'human' / f'{spec.id}-{time.strftime("%Y%m%d-%H%M")}').resolve()
  if run_dir.exists() and any(run_dir.iterdir()):
    parser.error(f'{run_dir} isn\'t empty; pass a new --run-dir')
  run_id = f'{spec.id}-{run_dir.name}-{uuid.uuid4().hex[:8]}'
  limits = dataclasses.replace(
    RunLimits(), max_steps=10**9, stuck_turn_s=1e9, run_deadline_s=args.hours * 3600,
    post_submit_grace_s=1.0, startup_timeout_s=600.0,
  )
  options = argparse.Namespace(
    agent='human', task=args.task, docker_image=None, task_image=TASK_IMAGE, model_config=None,
    command_timeout=None, model=None, effort=None, claude_auth=None, worker=None, hours=args.hours,
  )
  print(f'Setting up {spec.id} (about a minute)...', flush=True)
  try:
    record = asyncio.run(_cancel_on_sigterm(
      _execute(spec, options, run_dir, run_id, 'human', [], None, approve_all, limits),
    ))
  except (KeyboardInterrupt, asyncio.CancelledError):
    print(f'\nAbandoned; what there is stays in {run_dir}.', file=sys.stderr)
    return 130
  human.add_summary(run_dir)
  print(f'\nRun over: {record.outcome}. Grading...', flush=True)
  if record.outcome in (Outcome.COMPLETE, Outcome.BLOCKED):
    verdict = asyncio.run(grading.grade_run(run_dir))
    print(human.verdict_summary(verdict, json.loads((run_dir / 'record.json').read_text())))
  print(f'Everything is in {run_dir}.')
  return 0


def _shell(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
  info = args.run_dir / human.SHELL_FILE
  if not info.exists():
    parser.error(f'no human run is going in {args.run_dir} (start one with `python -m beambench human`)')
  os.execvp('docker', human.shell_command(json.loads(info.read_text())['container']))


def _batch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
  def names(value):
    return [item.strip() for item in value.split(',') if item.strip()] if value else []
  matrix = batch_module.load_matrix(args.matrix)
  if unknown := [name for name in names(args.configs) if name not in matrix.configs]:
    parser.error(f'no such config in {args.matrix.name}: {", ".join(unknown)}')
  cells = batch_module.plan(
    matrix, only_tasks=names(args.tasks), only_configs=names(args.configs),
    seeds=[int(seed) for seed in names(args.seeds)],
  )
  out = args.out.resolve()
  if args.status:
    print(batch_module.status_table(cells, out))
    return 0
  if args.report:
    print(costs.report(cells, out))
    return 0
  if args.dry_run:
    queues: dict[str, list] = {}
    for cell in cells:
      queues.setdefault(cell.config.queue, []).append(cell)
    for queue, queued in queues.items():
      states = [batch_module.cell_state(cell, out) for cell in queued]
      to_run = [cell for cell, state in zip(queued, states) if state != batch_module.DONE]
      print(f'{queue}: {len(queued)} cells, {len(to_run)} to run or grade')
      for cell in to_run[:5]:
        print(f'  {cell.task.id} / {cell.config.name} / seed {cell.seed}')
      if len(to_run) > 5:
        print(f'  ... and {len(to_run) - 5} more')
    return 0
  runner = batch_module.Batch(matrix, out, cells, max_parallel=args.max_parallel, rerun_stale=args.rerun_stale)
  try:
    asyncio.run(runner.run())
  except KeyboardInterrupt:
    print('Stopped. Run the same command again to resume.', file=sys.stderr)
    return 130
  print(batch_module.status_table(cells, out))
  return 0


def _login(args: argparse.Namespace) -> int:
  if args.agent == 'codex':
    return _login_codex(args.docker_image)
  name = LOGIN_KEYS[args.agent]
  ran_setup = args.agent == 'claude' and not args.paste_only
  if ran_setup:
    print('Running `claude setup-token`. When it prints the token, select all of it,')
    print('even if it wraps onto several lines, and copy it.\n')
    subprocess.run(['claude', 'setup-token'], check=True)
  value = secrets.read_pasted(f'\nPaste {name}, then press Enter on an empty line: ')
  if not value:
    print('Nothing pasted; nothing saved.')
    return 1
  if args.agent == 'claude' and not value.startswith('sk-ant-'):
    answer = input("That doesn't start with sk-ant-, like Claude tokens do. Save it anyway? [y/N] ")
    if answer.strip().lower() not in ('y', 'yes'):
      return 1
  secrets.save(name, value)
  if ran_setup:
    secrets.clear_screen()
  print(f'Saved {name} ({len(value)} characters) to {secrets.SECRETS_FILE}.')
  return 0


def _login_codex(image: str) -> int:
  """Sign Codex in with a ChatGPT account, using the device code flow in a container."""
  codex.AUTH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
  print('Signing Codex in to your ChatGPT account: open the link it shows and enter the code.\n')
  subprocess.run([
    'docker', 'run', '--rm', '--interactive', '--tty',
    '--user', f'{os.getuid()}:{os.getgid()}',
    '--env', 'CODEX_HOME=/codex-auth',
    '--volume', f'{codex.AUTH_DIR}:/codex-auth',
    image, 'codex', 'login', '--device-auth',
  ], check=True)
  auth = codex.AUTH_DIR / 'auth.json'
  if not auth.exists():
    print("Codex didn't save a sign-in.")
    return 1
  auth.chmod(0o600)
  print(f'Saved the Codex sign-in to {auth}.')
  return 0


def _run(parser: argparse.ArgumentParser, args: argparse.Namespace, limits: RunLimits) -> int:
  spec = tasks.load_task(args.task)
  track = 'neutral' if args.agent == 'neutral' else 'native'
  if track not in spec.tracks:
    parser.error(f'{spec.id} runs only on the {", ".join(spec.tracks)} track')
  if args.agent == 'neutral' and not args.model_config:
    parser.error('neutral needs --model-config')
  run_dir = args.run_dir.resolve()
  if run_dir.exists() and any(run_dir.iterdir()):
    parser.error(f'{run_dir} isn\'t empty; pass a new --run-dir')
  workspace = run_dir / 'workspace'
  submit_dir = run_dir / 'submit'
  state_dir = run_dir / args.agent
  run_id = f'{spec.id}-{run_dir.name}-{uuid.uuid4().hex[:8]}'

  if args.worker and args.agent not in ('claude', 'neutral'):
    parser.error('--worker is for --agent claude or neutral')
  if args.system_note and args.agent != 'neutral':
    parser.error('--system-note is for --agent neutral')
  if (args.reviewer or args.guard or args.submit_tool) and (args.agent != 'neutral' or args.worker):
    parser.error('--reviewer, --guard, and --submit-tool are for --agent neutral without a worker')
  if args.verifier and not args.reviewer:
    parser.error('--verifier needs --reviewer')
  credentials = dict(CREDENTIAL_ENV)
  if args.agent == 'claude' and args.claude_auth == 'api':
    credentials['claude'] = claude_code.API_KEY_ENV
  secret_names = [credentials[args.agent]] if args.agent in credentials else []
  config = neutral.load_models()[args.model_config] if args.agent == 'neutral' else None
  worker = neutral.load_models()[args.worker] if args.worker else None
  if worker:
    secret_names.append(worker.api_key_env)  # The worker calls its model from the container.
  needed = [*secret_names, *([config.api_key_env] if config else [])]
  if missing := secrets.load_into_environ(needed):
    login_name = next((key for key, env in LOGIN_KEYS.items() if env == missing[0]), '...')
    parser.error(f'no {missing[0]}: run `python -m beambench login {login_name}` or set it in your environment')
  if args.agent == 'codex' and not (codex.AUTH_DIR / 'auth.json').exists():
    parser.error('no Codex sign-in: run `python -m beambench login codex`')

  if args.approve_only:
    approve = approve_matching(args.approve_only)
  elif args.deny_all:
    approve = deny_all
  else:
    approve = approve_all
  limits = dataclasses.replace(
    limits, max_steps=args.max_steps, stuck_turn_s=args.stuck_turn, run_deadline_s=args.run_deadline,
  )
  try:
    record = asyncio.run(_cancel_on_sigterm(_execute(
      spec, args, run_dir, run_id, track, secret_names, config, approve, limits, worker,
    )))
  except (KeyboardInterrupt, asyncio.CancelledError):
    print('Stopped; the run was cleaned up and recorded nothing.', file=sys.stderr)
    return 130
  if worker:
    _add_worker_summary(run_dir)
  # Take the run's real credentials out of everything it left behind.
  known = {name: os.environ.get(name, '') for name in needed}
  if args.agent == 'codex':
    known.update(scrub.codex_secrets(codex.AUTH_DIR / 'auth.json'))
  report = scrub.scrub(run_dir, known)
  (run_dir / 'scrub.json').write_text(json.dumps(report, indent=2) + '\n')
  if report['unscrubbable']:
    print(f'warning: secrets left in binary files; don\'t publish them: {report["unscrubbable"]}', file=sys.stderr)
  print(json.dumps({
    'outcome': record.outcome,
    'detail': record.outcome_detail,
    'turns': record.turns,
    'steps': record.steps,
    'submit': record.submit,
    'usage': record.usage_total,
    'run_dir': str(run_dir),
  }, indent=2))
  return 1 if record.outcome == Outcome.INFRA_ERROR else 0


def _add_worker_summary(run_dir: Path) -> None:
  """Add the worker's commands, tokens, and API trouble (from its telemetry) to the run record."""
  path = run_dir / 'telemetry' / 'worker.jsonl'
  entries = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
  usage: dict = {}
  for entry in entries:
    if entry.get('event') == 'model_call':
      usage['requests'] = usage.get('requests', 0) + 1
      for key, value in neutral.flatten_usage(entry.get('usage')).items():
        usage[key] = usage.get(key, 0) + value
  record_path = run_dir / 'record.json'
  record = json.loads(record_path.read_text())
  record['worker'] = {
    'commands': sum(entry.get('event') == 'command' for entry in entries),
    'usage': usage,
    'retries': sum(entry.get('event') == 'retry' for entry in entries),
    'provider_errors': sum(entry.get('event') == 'provider_error' for entry in entries),
  }
  record_path.write_text(json.dumps(record, indent=2) + '\n')


def worker_env(worker: neutral.ModelConfig, command_timeout_s: float, max_commands: int) -> dict[str, str]:
  """The worker server's settings (container/beam_worker.py), the same for every brain."""
  return {
    'BEAMBENCH_WORKER_BASE_URL': worker.base_url, 'BEAMBENCH_WORKER_MODEL': worker.model,
    'BEAMBENCH_WORKER_PARAMS': json.dumps(worker.params), 'BEAMBENCH_WORKER_KEY_ENV': worker.api_key_env,
    'BEAMBENCH_WORKER_MAX_TOKENS': str(worker.max_tokens),
    'BEAMBENCH_WORKER_COMMAND_TIMEOUT_S': str(command_timeout_s),
    'BEAMBENCH_WORKER_MAX_COMMANDS': str(max_commands),
  }


async def _execute(spec, args, run_dir, run_id, track, secret_names, config, approve, limits, worker=None):
  """Build the workspace, start any sidecars, run the agent, and stop everything."""
  workspace = run_dir / 'workspace'
  submit_dir = run_dir / 'submit'
  state_dir = run_dir / args.agent
  telemetry_dir = run_dir / 'telemetry'
  for directory in (run_dir, submit_dir, state_dir, telemetry_dir):
    directory.mkdir(parents=True, exist_ok=True)
  agent_image = args.docker_image or AGENT_IMAGES[args.agent]
  await tasks.prepare_workspace(spec, workspace, args.task_image)
  mounts = [
    (workspace, '/workspace'), (submit_dir, '/harness/submit'), (telemetry_dir, TELEMETRY_DIR),
  ]
  if args.agent != 'neutral':
    mounts.append((state_dir, AGENTS[args.agent].STATE_DIR))
  mounts += tasks.prepare_home(spec, run_dir / 'home')
  name = 'beambench-' + re.sub(r'[^a-zA-Z0-9_.-]', '-', run_id)

  sidecars = []
  checks = None  # The scaffold's reviewer and guard, if this run has them.
  try:
    # The neutral harness calls its model from here, so its container needs no
    # network. A native agent's container joins only internal networks and
    # reaches its own API, and nothing else, through the egress proxy.
    networks, hosts, info = [], {}, {}
    env = dict(getattr(AGENTS[args.agent], 'CONTAINER_ENV', {}))
    if getattr(args, 'reviewer', False):
      env['BEAMBENCH_SUBMIT_TIMEOUT'] = str(scaffold.SUBMIT_TIMEOUT_S)  # The submit command waits for the review.
    if track == 'native' or worker:
      # A neutral brain calls its own model from here; only its worker, in
      # the container, needs a way out, to the worker's model API.
      hosts_allowed = list(AGENTS[args.agent].EGRESS_HOSTS) if track == 'native' else []
      if worker:
        hosts_allowed.append(httpx.URL(worker.base_url).host)
      egress = sidecar_module.Egress(name=f'{name}-egress', out_dir=run_dir / 'egress', hosts=hosts_allowed)
      await egress.start()
      sidecars.append(egress)
      networks.append(egress.network)
      env.update(egress.env(direct_hosts=spec.canary_hosts))
      info['egress'] = {'hosts': list(egress.hosts)}
    if spec.canary_hosts:
      canary = sidecar_module.Canary(name=f'{name}-canary', out_dir=run_dir / 'canary')
      await canary.start()
      sidecars.append(canary)
      networks.append(canary.network)
      hosts = {host: canary.ip for host in spec.canary_hosts}
      info['canary'] = {'hosts': list(spec.canary_hosts), 'ip': canary.ip}
    if spec.monitor_paths:
      monitor = sidecar_module.Monitor(
        name=f'{name}-monitor', out_dir=run_dir / 'monitor', mounts=mounts, paths=spec.monitor_paths,
      )
      await monitor.start()
      sidecars.append(monitor)
      info['monitor'] = {'paths': list(spec.monitor_paths)}
    container = Container(
      image=agent_image,
      name=name,
      mounts=mounts,
      env_from_host=secret_names,
      env=env,
      networks=networks or ['none'],
      extra_hosts=hosts,
      tmpfs=spec.tmpfs,
    )

    session: AgentSession
    if args.agent == 'mirror':
      session = mirror.AcpSession(
        mirror.mirror_command(f'{mirror.STATE_DIR}/state.db'),
        agent_cwd='/workspace',
        run_dir=run_dir,
        container=container,
      )
    elif args.agent == 'claude':
      brain_config = None
      if worker:
        # The worker's tool server, which Claude Code starts in the container; it
        # inherits the container's environment, the worker's API key included.
        (state_dir / 'mcp.json').write_text(json.dumps({'mcpServers': {'worker': {
          'type': 'stdio', 'command': 'python3', 'args': ['/usr/local/lib/beambench/beam_worker.py'],
          'timeout': 3_600_000,  # A delegation can run many commands; don't cut it off.
          'env': worker_env(worker, args.command_timeout or spec.command_timeout_s, limits.max_steps),
        }}}, indent=2) + '\n')
        brain_config = f'{claude_code.STATE_DIR}/mcp.json'
      session = claude_code.ClaudeCodeSession(
        run_dir=run_dir, model=args.model or claude_code.DEFAULT_MODEL, effort=args.effort,
        container=container, brain_mcp_config=brain_config,
        activity_files=[telemetry_dir / 'worker.jsonl'] if worker else (),
      )
    elif args.agent == 'codex':
      session = codex.CodexSession(
        run_dir=run_dir, model=args.model or codex.DEFAULT_MODEL, effort=args.effort,
        container=container, codex_home=state_dir, auth_file=codex.AUTH_DIR / 'auth.json',
      )
    elif args.agent == 'human':
      session = human.HumanSession(
        container=container, run_dir=run_dir, claim_names=list(spec.claims),
        intro=human.instructions(
          spec.id, spec.goal, spec.extra_claim_lines, workspace, run_dir, limits.run_deadline_s / 3600,
        ),
      )
    elif worker:
      session = neutral_brain.BrainSession(
        config=config,
        client=neutral.ChatClient(config, os.environ[config.api_key_env]),
        shell=neutral.ContainerShell(container),
        run_dir=run_dir,
        container=container,
        worker=neutral_brain.McpWorker(neutral_brain.worker_command(
          container, worker_env(worker, args.command_timeout or spec.command_timeout_s, limits.max_steps),
        )),
        command_timeout_s=args.command_timeout or spec.command_timeout_s,
      )
    else:
      shell = neutral.ContainerShell(container)
      if getattr(args, 'reviewer', False) or getattr(args, 'guard', False):
        checks = scaffold.Scaffold(
          config, os.environ[config.api_key_env], spec.goal, run_dir, shell,
          review=args.reviewer, guard=args.guard,
          verifier={'image': agent_image, 'name': name, 'workspace': workspace, 'tmpfs': spec.tmpfs}
          if getattr(args, 'verifier', False) else None,
          version=getattr(args, 'scaffold_version', scaffold.VERSION), max_steps=limits.max_steps,
          options=json.loads(args.scaffold_options) if getattr(args, 'scaffold_options', None) else None,
        )
      session = neutral.NeutralSession(
        config=config,
        client=neutral.ChatClient(config, os.environ[config.api_key_env]),
        shell=shell,
        run_dir=run_dir,
        container=container,
        command_timeout_s=args.command_timeout or spec.command_timeout_s,
        system_note=getattr(args, 'system_note', ''),
        submit_tool=getattr(args, 'submit_tool', False),
        guard=checks.check if checks and checks.guard_enabled else None,
        checkpoint=checks.progress if checks and checks.progress_enabled else None,
      )

    task = Task(
      run_id=run_id,
      goal=spec.goal,
      workspace=workspace,
      submit_dir=submit_dir,
      run_dir=run_dir,
      limits=limits,
      approve=approve,
      extra_claims=spec.extra_claim_lines,
      extra_claim_fields=tuple(spec.claims),
      restate_goal_in_nudges=spec.restate_goal_in_nudges,
      submit_tool=worker is not None or getattr(args, 'submit_tool', False),
      reviewer=checks.review if checks and checks.review_enabled else None,
      kickoff_note=getattr(args, 'kickoff_note', ''),
      review_submit=getattr(args, 'review_submit', False),
      info={
        'id': spec.id,
        'family': spec.family,
        'path': str(spec.path),
        'expected_status': spec.expected_status,
        'task_hash': tasks.task_hash(spec),
        'harness_hash': tasks.harness_hash(),
        'image': args.task_image,
        'image_id': await tasks.image_id(args.task_image),
        'agent_image': agent_image,
        'agent_image_id': await tasks.image_id(agent_image),
        'agent': args.agent,
        'track': track,
        'claude_auth': args.claude_auth if args.agent == 'claude' else None,
        'worker': dataclasses.asdict(worker) if worker else None,
        'kickoff_note': getattr(args, 'kickoff_note', '') or None,
        'system_note': getattr(args, 'system_note', '') or None,
        'review_submit': getattr(args, 'review_submit', False),
        'scaffold': {'reviewer': getattr(args, 'reviewer', False), 'guard': getattr(args, 'guard', False),
                     'submit_tool': getattr(args, 'submit_tool', False), 'verifier': getattr(args, 'verifier', False),
                     'version': checks.version_label if checks else scaffold.VERSION},
        'restate_goal_in_nudges': spec.restate_goal_in_nudges,
        **info,
      },
    )
    record = await run_task(task, session)
    if checks:
      record.scaffold = {'stats': checks.stats, 'usage': checks.usage}
      record.write(run_dir / 'record.json')
    return record
  finally:
    if checks:
      await checks.aclose()
    for sidecar in reversed(sidecars):
      await sidecar.stop()

if __name__ == '__main__':
  sys.exit(main())
