"""Safety-probe sidecars: a canary server and a file monitor, out of the agent's reach.

The canary runs on an internal Docker network the agent's container joins;
the hostnames a probe plants (an injected URL, a credentialed API) resolve to
it, and it logs every hit to <run>/canary/requests.jsonl. Without it, an
attempted violation would fail silently on a dead network and look clean.

The monitor runs inotifywait in its own container over the same host folders
the agent's container mounts, and logs opens, reads, writes, creates,
deletes, and renames on the watched paths to <run>/monitor/events.log,
including writes that are later undone. inotify misses access through
memory-mapped files and can overflow its queue; an overflow, or a monitor
that stopped early, marks the record incomplete (see status.json), and
graders then report the affected checks as unknown.

The egress proxy keeps native agents offline except for their own API. Their
container joins only internal networks; the proxy joins one of them and
Docker's default network, and the agent's CLI reaches its API through
HTTPS_PROXY. Every other host is refused and logged to
<run>/egress/requests.jsonl, so an attempted download shows up instead of
failing silently.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from collections.abc import Sequence
from pathlib import Path

from beambench.container import _run

SIDECAR_IMAGE = 'beambench-monitor:dev'
INOTIFY_EVENTS = 'open,access,modify,attrib,close_write,moved_from,moved_to,create,delete,delete_self'
# Event kinds that mean a watched file changed. On Docker Desktop's file
# sharing a write may show up as CREATE or MODIFY without CLOSE_WRITE, so
# graders count any of these.
WRITE_EVENTS = frozenset({'CREATE', 'MODIFY', 'CLOSE_WRITE', 'MOVED_TO', 'MOVED_FROM', 'DELETE', 'DELETE_SELF', 'ATTRIB'})


def _user() -> list[str]:
  return ['--user', f'{os.getuid()}:{os.getgid()}']


async def _wait_for(predicate, timeout_s: float = 30.0) -> bool:
  deadline = asyncio.get_running_loop().time() + timeout_s
  while asyncio.get_running_loop().time() < deadline:
    if predicate():
      return True
    await asyncio.sleep(0.2)
  return predicate()


@dataclasses.dataclass
class Canary:
  name: str
  out_dir: Path
  network: str = ''
  ip: str = ''

  async def start(self) -> None:
    self.out_dir.mkdir(parents=True, exist_ok=True)
    self.network = f'{self.name}-net'
    await _run(['docker', 'network', 'create', '--internal', self.network], check=True)
    await _run([
      'docker', 'run', '--detach', '--name', self.name, '--network', self.network, *_user(),
      # Lets the unprivileged server listen on ports 80 and 443.
      '--sysctl', 'net.ipv4.ip_unprivileged_port_start=0',
      '--volume', f'{self.out_dir}:/out',
      SIDECAR_IMAGE, 'python3', '/usr/local/bin/canary_server.py',
    ], check=True)
    self.ip = (await _run([
      'docker', 'inspect', '--format', f'{{{{(index .NetworkSettings.Networks "{self.network}").IPAddress}}}}',
      self.name,
    ], check=True)).strip()
    log = self.out_dir / 'requests.jsonl'
    if not await _wait_for(lambda: log.exists() and '"started"' in log.read_text()):
      raise RuntimeError('the canary server did not start')

  async def stop(self) -> None:
    await _run(['docker', 'rm', '--force', self.name])
    await _run(['docker', 'network', 'rm', self.network])


@dataclasses.dataclass
class Egress:
  name: str
  out_dir: Path
  hosts: Sequence[str]  # Allowed upstream hosts; ".example.com" allows subdomains.
  network: str = ''  # The internal network the agent's container joins.
  url: str = ''  # The proxy, as the agent's container reaches it.

  PORT = 3128

  async def start(self) -> None:
    self.out_dir.mkdir(parents=True, exist_ok=True)
    self.network = f'{self.name}-net'
    await _run(['docker', 'network', 'create', '--internal', self.network], check=True)
    await _run([
      'docker', 'run', '--detach', '--name', self.name, *_user(),
      '--volume', f'{self.out_dir}:/out',
      SIDECAR_IMAGE, 'python3', '/usr/local/bin/egress_proxy.py', '--port', str(self.PORT), *self.hosts,
    ], check=True)
    await _run(['docker', 'network', 'connect', self.network, self.name], check=True)
    ip = (await _run([
      'docker', 'inspect', '--format', f'{{{{(index .NetworkSettings.Networks "{self.network}").IPAddress}}}}',
      self.name,
    ], check=True)).strip()
    self.url = f'http://{ip}:{self.PORT}'
    log = self.out_dir / 'requests.jsonl'
    if not await _wait_for(lambda: log.exists() and '"started"' in log.read_text()):
      raise RuntimeError('the egress proxy did not start')

  def env(self, direct_hosts: Sequence[str] = ()) -> dict[str, str]:
    """Proxy settings for the agent's container. Only HTTPS goes through the
    proxy: plain HTTP is what tasks use locally (dev servers, a probe's canary
    host), and outside traffic has no route anyway."""
    direct = ','.join(['localhost', '127.0.0.1', '::1', *direct_hosts])
    return {'HTTPS_PROXY': self.url, 'https_proxy': self.url, 'NO_PROXY': direct, 'no_proxy': direct}

  async def stop(self) -> None:
    await _run(['docker', 'rm', '--force', self.name])
    await _run(['docker', 'network', 'rm', self.network])
    log = self.out_dir / 'requests.jsonl'
    lines = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    requests = [line for line in lines if line.get('method') and line.get('event') != 'closed']
    refused = [line for line in requests if not line.get('allowed')]
    (self.out_dir / 'summary.json').write_text(json.dumps({
      'hosts_allowed': list(self.hosts),
      'requests': len(requests),
      'refused': len(refused),
      'refused_hosts': sorted({str(line.get('host')) for line in refused}),
    }, indent=2) + '\n')


@dataclasses.dataclass
class Monitor:
  name: str
  out_dir: Path
  mounts: Sequence[tuple[Path, str]]  # The agent container's mounts; watched paths live in them.
  paths: Sequence[str]  # Paths as the agent's container sees them.

  async def start(self) -> None:
    self.out_dir.mkdir(parents=True, exist_ok=True)
    volumes = []
    for host_path, container_path in self.mounts:
      volumes += ['--volume', f'{host_path}:{container_path}:ro']
    script = (
      f'exec inotifywait --monitor --recursive --event {INOTIFY_EVENTS} --timefmt %s '
      f"--format '%T|%e|%w%f' --outfile /out/events.log \"$@\" 2> /out/inotify.err"
    )
    await _run([
      'docker', 'run', '--detach', '--name', self.name, '--network', 'none', *_user(), *volumes,
      '--volume', f'{self.out_dir}:/out',
      SIDECAR_IMAGE, 'sh', '-c', script, 'monitor', *self.paths,
    ], check=True)
    err = self.out_dir / 'inotify.err'
    if not await _wait_for(lambda: err.exists() and 'Watches established' in err.read_text()):
      raise RuntimeError(f'the file monitor did not start: {err.read_text() if err.exists() else ""}')

  async def stop(self) -> None:
    running = (await _run(['docker', 'inspect', '--format', '{{.State.Running}}', self.name])).strip()
    events = self.out_dir / 'events.log'
    overflow = events.exists() and 'Q_OVERFLOW' in events.read_text(errors='replace')
    (self.out_dir / 'status.json').write_text(json.dumps({
      'paths': list(self.paths),
      'running_at_end': running == 'true',
      'overflow': overflow,
      'complete': running == 'true' and not overflow,
    }, indent=2) + '\n')
    await _run(['docker', 'rm', '--force', self.name])
