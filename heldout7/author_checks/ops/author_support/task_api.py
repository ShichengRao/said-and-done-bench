"""Task folders: what the agent sees, how its workspace is built, how it's graded.

A task is a folder in tasks/:

  task.toml   id, family, expected status, extra claim fields, which tracks run it
  goal.md     the goal the agent is given
  workspace/  starting files, copied into the run's workspace
  home/       files for the agent's home folder, e.g. a canary ~/.aws (optional)
  setup/      setup.sh builds the rest of the workspace (git history, a package
              mirror) in an offline throwaway container; the agent never sees it
  grader/     grade.py and hidden tests, run on the snapshot after the run
  solutions/  reference outcomes the tests feed to the grader to validate it

Runs record a hash of the task folder and of the harness, so only runs on
the frozen versions count, and a grader-only fix can re-grade saved runs.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import os
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / 'tasks'
# What the agent saw or could do comes from these; changing any of them
# changes the harness hash.
_HARNESS_PATHS = ('beambench', 'container')
# Tools that run before or after an agent's run, not during it: changing them
# doesn't change what any agent saw. models.toml isn't here either: each run
# records its own model entry, and the batch compares that per config.
_OFFLINE_MODULES = ('batch.py', 'costs.py', 'grading.py', 'report.py', 'scrub.py', 'secrets.py')
# Files in the task folder that the agent's run doesn't depend on: changing
# them doesn't change the task hash, so graders can be fixed and runs
# re-graded. Everything else does.
_GRADING_ONLY = ('grader', 'solutions')


@dataclasses.dataclass(frozen=True)
class TaskSpec:
  id: str
  family: str
  path: Path
  goal: str
  expected_status: str  # 'complete' or 'blocked'
  claims: dict[str, str]  # Extra claim field -> what to put in it.
  tracks: tuple[str, ...]  # 'neutral', 'native'
  command_timeout_s: float
  tmpfs: dict[str, str] = dataclasses.field(default_factory=dict)  # [container] tmpfs
  canary_hosts: tuple[str, ...] = ()  # [canary] hosts: names that resolve to the canary server
  monitor_paths: tuple[str, ...] = ()  # [monitor] paths: watched for reads and writes
  restate_goal_in_nudges: bool = True  # [prompts]; off for rules that should be stated once

  @property
  def extra_claim_lines(self) -> tuple[str, ...]:
    return tuple(f'"{name}": {description}' for name, description in self.claims.items())


def load_task(path: Path) -> TaskSpec:
  path = path.resolve()
  meta = tomllib.loads((path / 'task.toml').read_text(encoding='utf-8'))
  if meta.get('expected_status') not in ('complete', 'blocked'):
    raise ValueError(f'{path}: expected_status must be "complete" or "blocked"')
  return TaskSpec(
    id=meta['id'],
    family=meta['family'],
    path=path,
    goal=(path / 'goal.md').read_text(encoding='utf-8'),
    expected_status=meta['expected_status'],
    claims=dict(meta.get('claims', {})),
    tracks=tuple(meta.get('tracks', ('neutral', 'native'))),
    command_timeout_s=float(meta.get('command_timeout_s', 600)),
    tmpfs=dict(meta.get('container', {}).get('tmpfs', {})),
    canary_hosts=tuple(meta.get('canary', {}).get('hosts', ())),
    monitor_paths=tuple(meta.get('monitor', {}).get('paths', ())),
    restate_goal_in_nudges=bool(meta.get('prompts', {}).get('restate_goal_in_nudges', True)),
  )


def task_hash(task: TaskSpec) -> str:
  """Everything in the task folder except the grader and reference solutions."""
  return _hash_tree(task.path, skip=_GRADING_ONLY)


def grader_hash(task: TaskSpec) -> str:
  return _hash_tree(task.path / 'grader')


def harness_hash() -> str:
  digest = hashlib.sha256()
  for name in _HARNESS_PATHS:
    digest.update(name.encode() + b'\0' + _hash_tree(ROOT / name, skip=_OFFLINE_MODULES).encode())
  return digest.hexdigest()


def _hash_tree(root: Path, skip: tuple[str, ...] = ()) -> str:
  digest = hashlib.sha256()
  if root.is_file():
    digest.update(root.read_bytes())
    return digest.hexdigest()
  for path in sorted(root.rglob('*')):
    relative = path.relative_to(root)
    if relative.parts[0] in skip or '__pycache__' in relative.parts or not path.is_file():
      continue
    digest.update(str(relative).encode() + b'\0' + path.read_bytes() + b'\0')
  return digest.hexdigest()


async def prepare_workspace(task: TaskSpec, workspace: Path, image: str) -> None:
  """Copy the starting files and run setup.sh against them, offline, in the task image."""
  workspace.mkdir(parents=True, exist_ok=True)
  if (task.path / 'workspace').is_dir():
    shutil.copytree(task.path / 'workspace', workspace, dirs_exist_ok=True)
  setup = task.path / 'setup' / 'setup.sh'
  if not setup.exists():
    return
  proc = await asyncio.create_subprocess_exec(
    'docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
    '--volume', f'{workspace}:/workspace',
    '--volume', f'{task.path / "setup"}:/task-setup:ro',
    '--workdir', '/workspace',
    image, 'bash', '/task-setup/setup.sh',
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
  )
  output, _ = await proc.communicate()
  if proc.returncode:
    raise RuntimeError(f'{task.id} setup failed ({proc.returncode}):\n{output.decode(errors="replace")[-2000:]}')


def prepare_home(task: TaskSpec, home: Path) -> list[tuple[Path, str]]:
  """Copy the task's home/ entries (e.g. a canary ~/.aws) and return their mounts.

  Each top-level entry is mounted on its own, so the image's own files in
  the agent's home (such as Mirror's config) stay visible.
  """
  source = task.path / 'home'
  if not source.is_dir():
    return []
  shutil.copytree(source, home, dirs_exist_ok=True)
  return [(home / entry.name, f'/home/agent/{entry.name}') for entry in sorted(home.iterdir())]


async def image_id(image: str) -> str:
  proc = await asyncio.create_subprocess_exec(
    'docker', 'image', 'inspect', '--format', '{{.Id}}', image,
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
  )
  output, _ = await proc.communicate()
  return output.decode().strip()
