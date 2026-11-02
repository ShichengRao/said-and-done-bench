"""A mock of the ledger, for development and the integration tests.

    python3 -m devtools.ledger_mock [--port 8770]            run in the foreground
    python3 -m devtools.ledger_mock --daemon [--port 8770]   run in the background (what the tests do)
    python3 -m devtools.ledger_mock --stop [--port 8770]     stop the background one

    POST /v1/totals          body {"source": ..., "deltas": {name: increment}}
    GET  /v1/totals/<name>   {"name": ..., "total": ...} (name percent-encoded)
    POST /v1/fail-next       the next POST /v1/totals fails with 503 (body {"fail": false} undoes that)
    GET  /healthz

Totals live in memory. Like the real ledger behind its load balancer, it
closes connections that have been idle for more than IDLE_TIMEOUT_S.
In the background it logs to /tmp/ledger-mock-<port>.log and keeps its pid
in /tmp/ledger-mock-<port>.pid.
"""

import argparse
import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

DEFAULT_PORT = 8770
IDLE_TIMEOUT_S = 1.0


class Ledger:
    def __init__(self):
        self.totals = {}
        self.fail_next = False
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    timeout = IDLE_TIMEOUT_S  # Applies to waiting for the next request on a kept-alive connection.
    ledger = None

    def do_GET(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if parts == ['healthz']:
            return self._send(200, {'ok': True})
        if len(parts) == 3 and parts[:2] == ['v1', 'totals']:
            name = unquote(parts[2])
            with self.ledger.lock:
                total = self.ledger.totals.get(name)
            if total is None:
                return self._send(404, {'error': 'no such total'})
            return self._send(200, {'name': name, 'total': total})
        return self._send(404, {'error': 'not found'})

    def do_POST(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        if parts == ['v1', 'fail-next']:
            try:
                fail = json.loads(raw).get('fail', True) if raw else True
            except (ValueError, AttributeError):
                return self._send(400, {'error': 'body must be a JSON object'})
            with self.ledger.lock:
                self.ledger.fail_next = bool(fail)
            return self._send(200, {'ok': True})
        if parts == ['v1', 'totals']:
            with self.ledger.lock:
                if self.ledger.fail_next:
                    self.ledger.fail_next = False
                    return self._send(503, {'error': 'unavailable'})
                try:
                    deltas = json.loads(raw)['deltas']
                    for name, increment in deltas.items():
                        self.ledger.totals[name] = self.ledger.totals.get(name, 0) + int(increment)
                except (ValueError, KeyError, TypeError, AttributeError) as error:
                    return self._send(400, {'error': str(error)})
            return self._send(200, {'ok': True, 'counters': len(deltas)})
        return self._send(404, {'error': 'not found'})

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write(f'ledger-mock: {self.address_string()} {format % args}\n')


def serve(port):
    handler = type('BoundHandler', (Handler,), {'ledger': Ledger()})
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    server.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f'ledger-mock listening on http://127.0.0.1:{port}', file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def pidfile(port):
    return f'/tmp/ledger-mock-{port}.pid'


def listening(port):
    try:
        socket.create_connection(('127.0.0.1', port), timeout=1).close()
        return True
    except OSError:
        return False


def daemon(port):
    """Start in the background (detached from the caller's session); return once it's listening."""
    child = os.fork()
    if child:
        os.waitpid(child, 0)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if listening(port):
                print(f'mock ledger running on http://127.0.0.1:{port} (stop it with '
                      f'`python3 -m devtools.ledger_mock --stop --port {port}`)')
                return 0
            time.sleep(0.1)
        print(f'the mock ledger didn\'t come up; see /tmp/ledger-mock-{port}.log', file=sys.stderr)
        return 1
    os.setsid()
    if os.fork():
        os._exit(0)
    log = os.open(f'/tmp/ledger-mock-{port}.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.dup2(log, 1)
    os.dup2(log, 2)
    with open(pidfile(port), 'w') as f:
        f.write(f'{os.getpid()}\n')
    try:
        serve(port)
    finally:
        os._exit(0)


def stop(port):
    try:
        pid = int(open(pidfile(port)).read())
    except (OSError, ValueError):
        print(f'no mock ledger pidfile for port {port}')
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            os.kill(pid, 0)
            time.sleep(0.1)
    except ProcessLookupError:
        pass
    os.remove(pidfile(port))
    print(f'stopped the mock ledger (pid {pid})')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Mock ledger.')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--daemon', action='store_true', help='run in the background')
    parser.add_argument('--stop', action='store_true', help='stop the background mock')
    args = parser.parse_args(argv)
    if args.stop:
        return stop(args.port)
    if args.daemon:
        return daemon(args.port)
    serve(args.port)
    return 0


if __name__ == '__main__':
    sys.exit(main())
