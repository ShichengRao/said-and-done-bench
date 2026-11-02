"""The egress proxy: native agents reach their own API and nothing else.

The proxy's rules run as a local process against a local echo server; the
sidecar runs against real containers, with example.com standing in for an
agent's API (so that test needs internet access, as the native agents do).
"""

import asyncio
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from beambench.container import Container
from beambench.sidecars import Egress
from tests.task_helpers import docker

PROXY = Path(__file__).resolve().parent.parent / 'container' / 'egress_proxy.py'
sys.path.insert(0, str(PROXY.parent))
from egress_proxy import allowed  # noqa: E402


def test_allowed_hosts_and_subdomains():
  hosts, ports = ['api.anthropic.com', '.reflection.ai'], {443}
  assert allowed('api.anthropic.com', 443, hosts, ports)
  assert allowed('API.Anthropic.com.', 443, hosts, ports)
  assert not allowed('api.anthropic.com', 80, hosts, ports)
  assert not allowed('evil-api.anthropic.com', 443, hosts, ports)
  assert allowed('reflection.ai', 443, hosts, ports) and allowed('api.reflection.ai', 443, hosts, ports)
  assert not allowed('notreflection.ai', 443, hosts, ports)
  assert not allowed('', 443, hosts, ports)


async def _echo_server():
  async def echo(reader, writer):
    while data := await reader.read(1024):
      writer.write(data)
      await writer.drain()
    writer.close()
  server = await asyncio.start_server(echo, '127.0.0.1', 0)
  return server, server.sockets[0].getsockname()[1]


async def _request(port, head, payload=b''):
  reader, writer = await asyncio.open_connection('127.0.0.1', port)
  writer.write(head)
  await writer.drain()
  status = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
  echoed = b''
  if payload and b' 200 ' in status:
    writer.write(payload)
    await writer.drain()
    echoed = await asyncio.wait_for(reader.readexactly(len(payload)), 5)
  writer.close()
  return status.split(b'\r\n', 1)[0].decode(), echoed


def test_proxy_tunnels_allowed_hosts_and_refuses_the_rest(tmp_path):
  async def scenario():
    server, echo_port = await _echo_server()
    log = tmp_path / 'requests.jsonl'
    proxy = await asyncio.create_subprocess_exec(
      sys.executable, str(PROXY), '--port', '0', '--ports', str(echo_port), '--out', str(log), '127.0.0.1',
    )
    try:
      for _ in range(100):
        if log.exists() and '"started"' in log.read_text():
          break
        await asyncio.sleep(0.05)
      port = json.loads(log.read_text().splitlines()[0])['port']
      tunnel = await _request(port, f'CONNECT 127.0.0.1:{echo_port} HTTP/1.1\r\n\r\n'.encode(), b'hello')
      other_host = await _request(port, f'CONNECT pypi.org:{echo_port} HTTP/1.1\r\n\r\n'.encode())
      other_port = await _request(port, b'CONNECT 127.0.0.1:443 HTTP/1.1\r\n\r\n')
      plain = await _request(port, b'GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n')
      await asyncio.sleep(0.2)  # The tunnel's closing line.
    finally:
      proxy.terminate()
      await proxy.wait()
      server.close()
    return tunnel, other_host, other_port, plain, [json.loads(line) for line in log.read_text().splitlines()]

  tunnel, other_host, other_port, plain, entries = asyncio.run(scenario())
  assert tunnel == ('HTTP/1.1 200 Connection established', b'hello')
  assert other_host[0].startswith('HTTP/1.1 403') and other_port[0].startswith('HTTP/1.1 403')
  assert plain[0].startswith('HTTP/1.1 403')
  requests = [entry for entry in entries if entry.get('method') and entry.get('event') != 'closed']
  assert [(entry['method'], entry['host'], entry['allowed']) for entry in requests] == [
    ('CONNECT', '127.0.0.1', True), ('CONNECT', 'pypi.org', False),
    ('CONNECT', '127.0.0.1', False), ('GET', 'example.com', False),
  ]
  closed = [entry for entry in entries if entry.get('event') == 'closed']
  assert closed and closed[0]['bytes_up'] == 5 and closed[0]['bytes_down'] == 5


@docker
def test_native_container_reaches_only_allowed_hosts(tmp_path):
  name = f'beambench-test-{uuid.uuid4().hex[:8]}'

  async def scenario():
    egress = Egress(name=f'{name}-egress', out_dir=tmp_path / 'egress', hosts=['example.com'])
    await egress.start()
    container = Container(
      image='beambench-task:dev', name=name, mounts=[], env=egress.env(), networks=[egress.network],
    )
    try:
      await container.start()
      script = (
        "curl -sS -m 20 -o /dev/null -w 'allowed:%{http_code}\\n' https://example.com/; "
        "curl -sS -m 20 -o /dev/null https://pypi.org/simple/ 2>&1 | sed 's/^/refused:/'; "
        "curl -sS -m 5 --noproxy '*' -o /dev/null https://example.com/ 2>&1 | sed 's/^/direct:/'; "
        "pip download --no-deps -q -d /tmp/x six 2>&1 | tail -1 | sed 's/^/pip:/'; true"
      )
      return await container.output(['sh', '-c', script])
    finally:
      await container.remove()
      await egress.stop()

  out = asyncio.run(scenario())
  assert 'allowed:200' in out
  assert 'refused:' in out and '403' in out
  assert 'direct:' in out and 'allowed:200' not in out.split('direct:', 1)[1]
  summary = json.loads((tmp_path / 'egress' / 'summary.json').read_text())
  assert 'pypi.org' in summary['refused_hosts'] and 'example.com' not in summary['refused_hosts']
  assert summary['hosts_allowed'] == ['example.com']
