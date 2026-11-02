"""An HTTPS proxy that lets a native agent reach only its own API hosts.

Native agents (Mirror, Claude Code, Codex) call their model APIs from inside
the run's container, but tasks are offline: anything else an agent tries,
such as `pip install` or fetching a page, has to fail, and be recorded. The
agent's container sits on an internal Docker network with no route out; this
proxy sits on that network and Docker's default one, and the agent's CLI
reaches its API through HTTPS_PROXY. It tunnels CONNECT requests to allowed
hosts and ports and answers everything else with 403 Forbidden.

Each request is a line in the log: allowed or not, and for tunnels, a second
line with the bytes moved when it closes. Only host names and ports are
logged; the tunneled traffic is TLS and isn't inspected.

Usage: egress_proxy.py [--port 3128] [--ports 443] [--out FILE] HOST [HOST ...]
A host starting with "." allows that domain and its subdomains.
"""

import argparse
import asyncio
import json
import time
from urllib.parse import urlsplit

_FORBIDDEN = b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
_BAD_GATEWAY = b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'


def allowed(host, port, hosts, ports):
    host = (host or '').lower().rstrip('.')
    if port not in ports or not host:
        return False
    for entry in hosts:
        if entry.startswith('.'):
            if host == entry[1:] or host.endswith(entry):
                return True
        elif host == entry:
            return True
    return False


class Proxy:
    def __init__(self, hosts, ports, out):
        self.hosts = [host.lower() for host in hosts]
        self.ports = set(ports)
        self.out = out

    def log(self, entry):
        with open(self.out, 'a', encoding='utf-8') as out:
            out.write(json.dumps({'time': round(time.time(), 3), **entry}) + '\n')

    async def handle(self, reader, writer):
        peer = writer.get_extra_info('peername')
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 30)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError, ConnectionError):
            writer.close()
            return
        parts = head.split(b'\r\n', 1)[0].decode('latin-1').split()
        method, target = (parts + ['', ''])[:2]
        entry = {'client': peer[0] if peer else None, 'method': method, 'target': target}
        if method != 'CONNECT':
            # Plain HTTP through the proxy: nothing the agents need.
            self.log({**entry, 'host': urlsplit(target).hostname, 'allowed': False})
            await self._refuse(writer, _FORBIDDEN)
            return
        host, _, port = target.rpartition(':')
        host, port = host.strip('[]'), int(port) if port.isdigit() else 0
        entry.update(host=host, port=port)
        if not allowed(host, port, self.hosts, self.ports):
            self.log({**entry, 'allowed': False})
            await self._refuse(writer, _FORBIDDEN)
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), 30)
        except (OSError, TimeoutError) as error:
            self.log({**entry, 'allowed': True, 'error': str(error) or type(error).__name__})
            await self._refuse(writer, _BAD_GATEWAY)
            return
        self.log({**entry, 'allowed': True})
        started = time.time()
        writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
        counts = {'bytes_up': 0, 'bytes_down': 0}
        await asyncio.gather(
            self._pipe(reader, upstream_writer, writer, counts, 'bytes_up'),
            self._pipe(upstream_reader, writer, upstream_writer, counts, 'bytes_down'),
        )
        for stream in (writer, upstream_writer):
            stream.close()
        self.log({**entry, 'event': 'closed', **counts, 'seconds': round(time.time() - started, 3)})

    @staticmethod
    async def _pipe(source, sink, other, counts, key):
        """Copy one direction of a tunnel; on an error, close both sides so the other direction ends too."""
        try:
            while data := await source.read(65536):
                counts[key] += len(data)
                sink.write(data)
                await sink.drain()
            if sink.can_write_eof():
                sink.write_eof()
        except (ConnectionError, OSError):
            sink.close()
            other.close()

    @staticmethod
    async def _refuse(writer, response):
        try:
            writer.write(response)
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        writer.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=3128)
    parser.add_argument('--ports', type=int, nargs='+', default=[443], help='upstream ports a tunnel may use')
    parser.add_argument('--out', default='/out/requests.jsonl')
    parser.add_argument('hosts', nargs='*')
    args = parser.parse_args()
    proxy = Proxy(args.hosts, args.ports, args.out)
    server = await asyncio.start_server(proxy.handle, '0.0.0.0', args.port)
    proxy.log({'event': 'started', 'port': server.sockets[0].getsockname()[1], 'hosts': proxy.hosts})
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
