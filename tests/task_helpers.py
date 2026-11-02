"""Helpers for grader-validation tests: build a task's real workspace, act out an
outcome, and grade it the way a real run would be graded.

Each task's tests (tests/test_task_<id>.py) use these to check that its
grader scores reference outcomes as intended before any run on it counts.
"""

import asyncio
import json
import os
import shutil
import subprocess

import pytest

from beambench.grading import grade_run
from beambench.snapshot import snapshot_workspace
from beambench.tasks import ROOT, TASKS_DIR, load_task, prepare_workspace, task_hash

IMAGE = 'beambench-task:dev'
# The held-out tasks live outside tasks/; pass tasks_dir=HELDOUT_DIR (or HELDOUT2_DIR, the
# second round, or HELDOUT3_DIR, the third) to use them, or SCENARIOS_DIR for the no-valid-option scenarios.
HELDOUT_DIR = ROOT / 'heldout'
HELDOUT2_DIR = ROOT / 'heldout2'
HELDOUT3_DIR = ROOT / 'heldout3'
SCENARIOS_DIR = ROOT / 'scenarios'
docker = pytest.mark.skipif(
  shutil.which('docker') is None
  or subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True).returncode != 0,
  reason=f'needs Docker and the {IMAGE} image',
)


def in_container(workspace, script, tmpfs=None):
  """Run a bash script in the task image against the workspace, as an agent would."""
  extra = []
  for path, size in (tmpfs or {}).items():
    extra += ['--tmpfs', f'{path}:size={size},mode=1777']
  return subprocess.run(
    ['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
     '--volume', f'{workspace}:/workspace', '--workdir', '/workspace', *extra,
     '--env', 'GIT_CONFIG_GLOBAL=/dev/null',
     IMAGE, 'bash', '-c', f'set -e; {script}'],
    check=True, capture_output=True, text=True,
  )


def graded(
  tmp_path, task_name, outcome, script=None, files=None,
  claims=None, telemetry=None, terminal_state=None, tasks_dir=TASKS_DIR,
):
  """Build the task's workspace, change it, and grade it as a run that ended in `outcome`.

  script runs in the task image against the workspace; files maps workspace
  paths to files to copy in. claims become the accepted submit's claims,
  telemetry a list of pytest.jsonl entries, and terminal_state the record's
  processes and sockets at the end.
  """
  spec = load_task(tasks_dir / task_name)
  run_dir = tmp_path / 'run'
  workspace = run_dir / 'workspace'
  asyncio.run(prepare_workspace(spec, workspace, IMAGE))
  for relative, source in (files or {}).items():
    shutil.copyfile(source, workspace / relative)
  if script:
    in_container(workspace, script, spec.tmpfs)
  snapshot_workspace(workspace, run_dir / 'snapshot.tar.gz')
  (run_dir / 'telemetry').mkdir()
  if telemetry:
    (run_dir / 'telemetry' / 'pytest.jsonl').write_text(''.join(json.dumps(entry) + '\n' for entry in telemetry))
  (run_dir / 'record.json').write_text(json.dumps({
    'outcome': outcome,
    'task': {'path': str(spec.path), 'task_hash': task_hash(spec), 'image': IMAGE},
    'submit': {'status': outcome, 'claims': claims} if claims is not None else None,
    'terminal_state': terminal_state,
  }))
  return asyncio.run(grade_run(run_dir))


def scripted_run(tmp_path, task_name, scripts, outcome='complete', claims=None, track='neutral', timeout_s=120,
                 tasks_dir=TASKS_DIR):
  """Run a task the way a real run does, with scripted commands instead of a model.

  Builds the workspace and home files, starts the canary and file monitor if
  the task asks for them, runs each script in the agent's container (on the
  canary network, with no other network for the neutral track), then
  snapshots, records the end-of-run state, and grades. Returns
  (verdict, outputs), outputs being each script's (output, exit code).
  """
  return asyncio.run(_scripted_run(tmp_path, task_name, scripts, outcome, claims, track, timeout_s, tasks_dir))


async def _scripted_run(tmp_path, task_name, scripts, outcome, claims, track, timeout_s, tasks_dir=TASKS_DIR):
  import uuid

  from beambench.container import Container
  from beambench.neutral import ContainerShell
  from beambench.outcomes import utc_now
  from beambench.sidecars import Canary, Monitor
  from beambench.tasks import prepare_home

  spec = load_task(tasks_dir / task_name)
  started_at = utc_now()
  run_dir = tmp_path / 'run'
  workspace = run_dir / 'workspace'
  submit_dir, telemetry_dir = run_dir / 'submit', run_dir / 'telemetry'
  for directory in (submit_dir, telemetry_dir):
    directory.mkdir(parents=True, exist_ok=True)
  await prepare_workspace(spec, workspace, IMAGE)
  from beambench.container import TELEMETRY_DIR
  mounts = [(workspace, '/workspace'), (submit_dir, '/harness/submit'), (telemetry_dir, TELEMETRY_DIR)]
  mounts += prepare_home(spec, run_dir / 'home')
  name = f'beambench-test-{uuid.uuid4().hex[:8]}'
  sidecars, networks, hosts = [], (['none'] if track == 'neutral' else []), {}
  outputs, terminal_state, snapshot = [], None, None
  try:
    if spec.canary_hosts:
      canary = Canary(name=f'{name}-canary', out_dir=run_dir / 'canary')
      await canary.start()
      sidecars.append(canary)
      networks = [canary.network] if track == 'neutral' else ['bridge', canary.network]
      hosts = {host: canary.ip for host in spec.canary_hosts}
    if spec.monitor_paths:
      monitor = Monitor(name=f'{name}-monitor', out_dir=run_dir / 'monitor', mounts=mounts, paths=spec.monitor_paths)
      await monitor.start()
      sidecars.append(monitor)
    container = Container(
      image=IMAGE, name=name, mounts=mounts, networks=networks, extra_hosts=hosts, tmpfs=spec.tmpfs,
    )
    await container.start()
    try:
      shell = ContainerShell(container)
      for script in ([scripts] if isinstance(scripts, str) else scripts):
        outputs.append(await shell.run(script, timeout_s))
      await asyncio.sleep(1)  # Let the monitor flush its last events.
      snapshot = snapshot_workspace(workspace, run_dir / 'snapshot.tar.gz')
      terminal_state = await container.terminal_state()
    finally:
      await container.remove()
  finally:
    for sidecar in reversed(sidecars):
      await sidecar.stop()
  (run_dir / 'record.json').write_text(json.dumps({
    'outcome': outcome,
    'started_at': started_at,
    'ended_at': utc_now(),
    'snapshot': snapshot,
    'task': {'path': str(spec.path), 'task_hash': task_hash(spec), 'image': IMAGE, 'track': track},
    'submit': {'status': outcome, 'claims': claims} if claims is not None else None,
    'terminal_state': terminal_state,
  }))
  return await grade_run(run_dir), outputs
