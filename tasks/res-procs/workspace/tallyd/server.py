"""tallyd's HTTP API.

    GET  /healthz
    GET  /v1/counters/<name>          {"name": ..., "value": ...}
    POST /v1/counters/<name>/incr     body {"by": n} (optional, default 1)
    POST /v1/batch                    body {"increments": [{"name": ..., "by": n}, ...]}
    GET  /v1/top?n=10                 {"counters": [{"name": ..., "value": ...}, ...]}
    POST /v1/flush                    send the increments since the last flush to the ledger now

Names in paths are percent-encoded (tallyd.client does this). tallyd also
flushes to the ledger on its own every --flush-every seconds.

    python3 -m tallyd.server [--host 127.0.0.1] [--port 8765] [--ledger URL] [--flush-every 10]
"""

import argparse
import http.client
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from tallyd.ledger import Ledger, LedgerError
from tallyd.store import InvalidName, Store

DEFAULT_PORT = 8765
DEFAULT_LEDGER = 'http://127.0.0.1:8770'


class Flusher:
    """Sends the store's increments to the ledger."""

    def __init__(self, store, ledger):
        self.store = store
        self.ledger = ledger
        self._lock = threading.Lock()

    def flush(self):
        """Send the increments since the last flush; return how many counters that covered."""
        with self._lock:
            deltas = self.store.take_deltas()
            if not deltas:
                return 0
            try:
                self.ledger.send(deltas)
            except (OSError, http.client.HTTPException, LedgerError) as error:
                print(f'tallyd: flush failed: {error!r}', file=sys.stderr, flush=True)
                return 0
            return len(deltas)

    def every(self, seconds):
        stop = threading.Event()

        def loop():
            while not stop.wait(seconds):
                self.flush()

        threading.Thread(target=loop, name='flusher', daemon=True).start()
        return stop


class Handler(BaseHTTPRequestHandler):
    # Keep-alive, so the dashboard's polling doesn't open a connection per request.
    protocol_version = 'HTTP/1.1'
    store = None  # Set by make_server().
    flusher = None

    def do_GET(self):
        url = urlsplit(self.path)
        parts = url.path.strip('/').split('/')
        if parts == ['healthz']:
            return self._send_json(200, {'ok': True})
        if len(parts) == 3 and parts[:2] == ['v1', 'counters']:
            name = parts[2]
            value = self.store.get(name)
            if value is None:
                return self._send_json(404, {'error': f'no counter named {name!r}'})
            return self._send_json(200, {'name': name, 'value': value})
        if parts == ['v1', 'top']:
            try:
                n = int(parse_qs(url.query).get('n', ['10'])[0])
            except ValueError:
                return self._send_json(400, {'error': 'n must be an integer'})
            return self._send_json(200, {'counters': [{'name': k, 'value': v} for k, v in self.store.top(n)]})
        return self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        try:
            body = self._read_json()
            if len(parts) == 4 and parts[:2] == ['v1', 'counters'] and parts[3] == 'incr':
                name = parts[2]
                value = self.store.incr(name, body.get('by', 1))
                return self._send_json(200, {'name': name, 'value': value})
            if parts == ['v1', 'batch']:
                results = []
                for item in body.get('increments', []):
                    value = self.store.incr(item['name'], item.get('by', 1))
                    results.append({'name': item['name'], 'value': value})
                return self._send_json(200, {'counters': results})
            if parts == ['v1', 'flush']:
                return self._send_json(200, {'flushed': self.flusher.flush()})
        except (ValueError, KeyError, TypeError, AttributeError, InvalidName) as error:
            return self._send_json(400, {'error': str(error)})
        return self._send_json(404, {'error': 'not found'})

    def _read_json(self):
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        body = json.loads(raw) if raw else {}
        if not isinstance(body, dict):
            raise ValueError('the body must be a JSON object')
        return body

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        sys.stderr.write(f'tallyd: {self.address_string()} {format % args}\n')


def make_server(host='127.0.0.1', port=DEFAULT_PORT, store=None, ledger_url=DEFAULT_LEDGER):
    store = store or Store()
    flusher = Flusher(store, Ledger(ledger_url))
    handler = type('BoundHandler', (Handler,), {'store': store, 'flusher': flusher})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    server.flusher = flusher
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description='Serve tallyd.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--ledger', default=os.environ.get('TALLYD_LEDGER', DEFAULT_LEDGER))
    parser.add_argument('--flush-every', type=float, default=10.0, help='seconds; 0 turns periodic flushes off')
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port, ledger_url=args.ledger)
    if args.flush_every > 0:
        server.flusher.every(args.flush_every)
    print(f'tallyd listening on http://{args.host}:{args.port}, flushing to {args.ledger}', file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
