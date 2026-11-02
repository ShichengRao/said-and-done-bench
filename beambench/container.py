"""One long-lived container per run; agent processes start in it with docker exec.

The container runs as this machine's user so files in the bind mounts stay
ours. Secrets such as API keys are passed by name (`--env NAME`), so they
never appear in a command line or a run record.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

# Every agent process records its pid here, so interrupt() can signal it;
# signaling the local `docker exec` client wouldn't reach it.
_PID_FILE = '/tmp/beambench-agent.pid'
# Mount a run's telemetry folder here and start() runs the collector that
# fills it (container/beambench_telemetryd.py), as root: the agent's user
# can't enter /var/lib/beambench, so it can't read or edit what's recorded.
TELEMETRY_DIR = '/var/lib/beambench/telemetry'
_TELEMETRY_SOCKET = '/run/beambench/telemetry.sock'


class ContainerError(Exception):
  pass


@dataclasses.dataclass
class Container:
  image: str
  name: str
  mounts: Sequence[tuple[Path, str]]
  env_from_host: Sequence[str] = ()
  env: Mapping[str, str] = dataclasses.field(default_factory=dict)
  # Networks to join, e.g. ['none'] for the neutral track, or a canary network
  # alongside the default one; empty means Docker's default.
  networks: Sequence[str] = ()
  # Host names that resolve to fixed addresses, e.g. a probe's canary host.
  extra_hosts: Mapping[str, str] = dataclasses.field(default_factory=dict)
  # Size-limited scratch space, e.g. {'/scratch': '600m'}: a disk quota the
  # agent can actually hit, unlike a limit on the container's writable layer.
  tmpfs: Mapping[str, str] = dataclasses.field(default_factory=dict)

  def run_command(self) -> list[str]:
    command = [
      'docker', 'run', '--detach', '--init', '--name', self.name,
      '--user', f'{os.getuid()}:{os.getgid()}',
    ]
    # Docker won't attach the default network and a user-defined one at
    # creation, so the first network goes here and start() connects the rest.
    if self.networks:
      command += ['--network', self.networks[0]]
    for host, address in self.extra_hosts.items():
      command += ['--add-host', f'{host}:{address}']
    for name in self.env_from_host:
      command += ['--env', name]
    for key, value in self.env.items():
      command += ['--env', f'{key}={value}']
    for host_path, container_path in self.mounts:
      command += ['--volume', f'{host_path}:{container_path}']
    for path, size in self.tmpfs.items():
      command += ['--tmpfs', f'{path}:size={size},mode=1777']
    if any(path == TELEMETRY_DIR for _, path in self.mounts):
      # The collector (root) reads senders' working directories; the agent's
      # user, not being root, gets no capabilities from this.
      command += ['--cap-add', 'SYS_PTRACE']
    return [*command, self.image, 'sleep', 'infinity']

  def exec_command(self, command: Sequence[str]) -> list[str]:
    return [
      'docker', 'exec', '--interactive', self.name,
      'sh', '-c', f'echo $$ > {_PID_FILE} && exec "$@"', 'agent', *command,
    ]

  async def start(self) -> None:
    await _run(self.run_command(), check=True)
    for network in self.networks[1:]:
      await _run(['docker', 'network', 'connect', network, self.name], check=True)
    if any(path == TELEMETRY_DIR for _, path in self.mounts):
      await _run([
        'docker', 'exec', '--user', '0', '--detach', self.name,
        'python3', '/usr/local/lib/beambench/telemetryd.py',
      ], check=True)
      for _ in range(50):
        try:
          await _run(['docker', 'exec', self.name, 'test', '-S', _TELEMETRY_SOCKET], check=True)
          break
        except ContainerError:
          await asyncio.sleep(0.2)
      else:
        raise ContainerError('the telemetry collector did not start')
      # A marker in the run's telemetry folder: graders can tell "the collector
      # got nothing" (nothing ran) from "there was no collector".
      host_dir = next(host for host, path in self.mounts if path == TELEMETRY_DIR)
      (Path(host_dir) / 'collector.json').write_text(json.dumps({'started': time.time()}) + '\n')

  async def output(self, command: Sequence[str]) -> str:
    """Run a short command in the container and return its stdout."""
    return await _run(['docker', 'exec', self.name, *command], check=True)

  async def terminal_state(self) -> dict:
    """What's running and listening in the container when a run ends."""
    try:
      processes = await self.output(['ps', '-eo', 'pid,ppid,pgid,etimes,args'])
      sockets = await self.output(['sh', '-c', 'cat /proc/net/tcp /proc/net/tcp6 2>/dev/null'])
      # Usage of each scratch quota, read by the harness rather than the agent.
      disk = await self.output(['df', '-B1', *self.tmpfs]) if self.tmpfs else ''
    except (ContainerError, TimeoutError) as error:
      return {'error': str(error)}
    return {'processes': processes, 'tcp': sockets, 'tmpfs_df': disk}

  async def pause(self) -> bool:
    """Freeze every process in the container; return whether it worked."""
    try:
      await _run(['docker', 'pause', self.name], check=True)
    except (ContainerError, TimeoutError):
      return False
    return True

  async def unpause(self) -> None:
    await _run(['docker', 'unpause', self.name])

  async def interrupt(self) -> None:
    """Send SIGINT to the most recently started agent process."""
    await _run(['docker', 'exec', self.name, 'sh', '-c', f'kill -INT "$(cat {_PID_FILE})"'])

  async def remove(self) -> None:
    await _run(['docker', 'rm', '--force', self.name])


async def _run(command: list[str], check: bool = False, timeout_s: float = 120) -> str:
  proc = await asyncio.create_subprocess_exec(
    *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
  )
  try:
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_s)
  except TimeoutError:
    proc.kill()
    await proc.wait()
    raise
  if check and proc.returncode:
    raise ContainerError(
      f'{" ".join(command[:3])} failed ({proc.returncode}): {stderr.decode(errors="replace")[-500:]}'
    )
  return stdout.decode(errors='replace')
