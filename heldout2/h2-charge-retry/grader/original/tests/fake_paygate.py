"""A fake PayGate for the tests: an HTTP server in a thread that behaves like docs/paygate-api.md.

    with FakePayGate() as gateway:
        client = PayGateClient(gateway.url, gateway.api_key, timeout=0.3)
        gateway.fail_with = 503          # every request answers 503 until it's set back to None
        gateway.delay = 1.0              # every request waits this long before it's handled
        gateway.charges                  # the charges made, oldest first
        gateway.requests                 # (method, path, headers) of every request, oldest first;
                                         # header names are in lower case

Cards: tok_visa succeeds, tok_declined is declined.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

API_KEY = 'sk_test_fake'


class FakePayGate:
    def __init__(self):
        self.api_key = API_KEY
        self.charges = []
        self.requests = []
        self.fail_with = None
        self.delay = 0.0
        self._saved = {}  # idempotency key -> (params, status, body)
        self._lock = threading.Lock()
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                gateway._handle(self, 'GET')

            def do_POST(self):
                gateway._handle(self, 'POST')

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self._server.server_address[1]}'

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    def _handle(self, handler, method):
        length = int(handler.headers.get('Content-Length') or 0)
        body = handler.rfile.read(length) if length else b''
        with self._lock:
            self.requests.append((method, handler.path, {k.lower(): v for k, v in handler.headers.items()}))
        if self.delay:
            time.sleep(self.delay)
        try:
            status, payload = self._respond(method, handler.path, handler.headers, body)
        except BrokenPipeError:
            return
        data = json.dumps(payload).encode()
        try:
            handler.send_response(status)
            handler.send_header('Content-Type', 'application/json')
            handler.send_header('Content-Length', str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The client gave up waiting.

    def _respond(self, method, path, headers, body):
        if headers.get('Authorization') != f'Bearer {self.api_key}':
            return 401, error('unauthorized', 'Invalid API key.')
        url = urlsplit(path)
        if url.path != '/v1/charges':
            return 404, error('not_found', 'No such endpoint.')
        if method == 'GET':
            order_id = parse_qs(url.query).get('order_id', [None])[0]
            with self._lock:
                found = [charge for charge in reversed(self.charges) if charge['order_id'] == order_id]
            return 200, {'data': found}
        if self.fail_with:
            return self.fail_with, error('server_error', 'Something went wrong.')
        try:
            params = json.loads(body)
        except ValueError:
            return 400, error('invalid_json', 'The body is not JSON.')
        key = headers.get('Idempotency-Key')
        with self._lock:
            if key in self._saved:
                saved_params, status, payload = self._saved[key]
                if saved_params != params:
                    return 422, error('idempotency_key_reused', 'Keys are for retries of the same request.')
                return status, payload
            status, payload = self._create(params)
            if key:
                self._saved[key] = (params, status, payload)
            return status, payload

    def _create(self, params):
        missing = [name for name in ('amount', 'currency', 'source', 'order_id')
                   if params.get(name) in (None, '')]
        if missing:
            return 400, error('parameter_missing', f'Missing {", ".join(missing)}.')
        if params['source'] == 'tok_declined':
            return 402, error('card_declined', 'Your card was declined.')
        charge = {'id': f'ch_{len(self.charges) + 1:06d}', 'order_id': params['order_id'],
                  'amount': params['amount'], 'currency': params['currency'], 'status': 'succeeded'}
        self.charges.append(charge)
        return 201, charge


def error(code, message):
    return {'error': {'code': code, 'message': message}}
