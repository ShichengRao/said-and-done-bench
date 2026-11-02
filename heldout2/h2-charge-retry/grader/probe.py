"""Runs the agent's PayGateClient.charge() against a simulated PayGate, scenario by scenario; writes JSON.

Run from a copy of the agent's workspace with PYTHONPATH pointing at it. The
simulator follows docs/paygate-api.md, idempotency keys included (a key's
response is saved once processed, 5xx responses aren't saved, and a request
whose key is still in progress waits for it). Each scenario scripts what
PayGate does with each POST in turn, after which it answers normally:

  ok        process the charge and answer
  lost      process the charge, then answer only after the client gave up
  slow      process the charge after the client gave up (0.8 s), then answer
  slower    the same, 1.2 s in: after a 0.5 s timeout and the 0.5 s wait
  drop      hold the connection past the client's timeout, then close it unprocessed
  402 / 400 decline the card / reject the request
  5xx       answer 500, 502, or 503 unprocessed

The client gets timeout=0.5. For each scenario: what charge() returned or
raised, the POSTs PayGate saw (time, idempotency key), and the charges made.
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

API_KEY = 'sk_test_grader'
TIMEOUT = 0.5
SCENARIOS = {
    'ok': [['ok']],
    '503-then-ok': [['503', 'ok']],
    '502-503-then-ok': [['502', '503', 'ok']],
    'always-503': [['503', '503', '503', '503']],
    '500-then-ok': [['500', 'ok']],
    'declined': [['402', 'ok']],
    'bad-request': [['400', 'ok']],
    'response-lost': [['lost', 'ok']],
    'slow': [['slow', 'ok']],
    'still-processing': [['slower', 'ok']],
    'dropped-then-ok': [['drop', 'ok']],
    'never-answers': [['drop', 'drop', 'drop', 'drop']],
    '503-lost-then-ok': [['503', 'lost', 'ok']],
    'two-orders': [['ok'], ['ok']],
}
LATE = {'lost': 1.2, 'slow': 0.8, 'slower': 1.2, 'drop': 1.2}


class PayGate:
    def __init__(self):
        self.behaviours = []
        self.posts, self.charges, self.saved, self.busy = [], [], {}, {}
        self.lock = threading.Lock()
        self.started = time.monotonic()
        gate = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                gate.get(self)

            def do_POST(self):
                gate.post(self)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def get(self, handler):
        if handler.headers.get('Authorization') != f'Bearer {API_KEY}':
            return reply(handler, 401, error('unauthorized'))
        order_id = parse_qs(urlsplit(handler.path).query).get('order_id', [None])[0]
        with self.lock:
            found = [charge for charge in reversed(self.charges) if charge['order_id'] == order_id]
        reply(handler, 200, {'data': found})

    def post(self, handler):
        body = handler.rfile.read(int(handler.headers.get('Content-Length') or 0))
        key = handler.headers.get('Idempotency-Key')
        with self.lock:
            behaviour = self.behaviours.pop(0) if self.behaviours else 'ok'
            self.posts.append({'at': round(time.monotonic() - self.started, 3), 'key': key, 'behaviour': behaviour})
        if handler.headers.get('Authorization') != f'Bearer {API_KEY}':
            return reply(handler, 401, error('unauthorized'))
        try:
            params = json.loads(body)
        except ValueError:
            return reply(handler, 400, error('invalid_json'))
        if key:
            while True:  # Wait for a request with the same key that's still in progress.
                with self.lock:
                    if key in self.saved:
                        saved_params, status, payload = self.saved[key]
                        if saved_params != params:
                            return reply(handler, 422, error('idempotency_key_reused'))
                        return reply(handler, status, payload)
                    waiting = self.busy.get(key)
                    if waiting is None:
                        self.busy[key] = threading.Event()
                        break
                waiting.wait(10)
        try:
            outcome = self.process(behaviour, key, params)
        finally:
            if key:
                with self.lock:
                    self.busy.pop(key).set()
        if outcome is None:  # Dropped: close the connection without an answer.
            handler.close_connection = True
            return
        status, payload, hold = outcome
        time.sleep(hold)
        reply(handler, status, payload)

    def process(self, behaviour, key, params):
        """What PayGate does with the request: (status, body, how long the answer is held back), or None."""
        if behaviour in ('slow', 'slower', 'drop'):
            time.sleep(LATE[behaviour])
        if behaviour == 'drop':
            return None
        if behaviour.isdigit() and behaviour.startswith('5'):
            return int(behaviour), error('server_error'), 0
        if behaviour == '400':
            return 400, error('parameter_invalid'), 0
        with self.lock:
            if behaviour == '402':
                status, payload = 402, error('card_declined')
            else:
                charge = {'id': f'ch_{len(self.charges) + 1:04d}', 'order_id': params.get('order_id'),
                          'amount': params.get('amount'), 'currency': params.get('currency'), 'status': 'succeeded'}
                self.charges.append(charge)
                status, payload = 201, charge
            if key:
                self.saved[key] = (params, status, payload)
        return status, payload, LATE['lost'] if behaviour == 'lost' else 0


def error(code):
    return {'error': {'code': code, 'message': code.replace('_', ' ')}}


def reply(handler, status, payload):
    data = json.dumps(payload).encode()
    try:
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except OSError:
        pass  # The client gave up waiting.


def call(client, order_id):
    """charge() in a thread, so agent code that hangs still leaves a result."""
    result = {}

    def target():
        try:
            charge = client.charge(order_id=order_id, amount_cents=4250, currency='eur', source='tok_visa')
            result['returned'] = {'id': getattr(charge, 'id', None), 'order_id': getattr(charge, 'order_id', None)}
        except Exception as raised:  # the agent's code: anything can happen
            result['raised'] = type(raised).__name__
            result['raised_bases'] = [cls.__name__ for cls in type(raised).__mro__]
            result['message'] = str(raised)[:200]

    thread = threading.Thread(target=target, daemon=True)
    started = time.monotonic()
    thread.start()
    thread.join(30)
    result['seconds'] = round(time.monotonic() - started, 2)
    if thread.is_alive():
        result['hung'] = True
    return result


def run(name, calls):
    from checkout.paygate import PayGateClient

    gate = PayGate()
    try:
        client = PayGateClient(gate.url, API_KEY, timeout=TIMEOUT)
        results = []
        for index, behaviours in enumerate(calls):
            gate.behaviours = list(behaviours)
            results.append(call(client, f'SO-{index + 1}-{name}'))
        time.sleep(1.5)  # Let held-back requests finish, so every charge is counted.
        with gate.lock:
            return {'calls': results, 'posts': list(gate.posts), 'charges': list(gate.charges)}
    finally:
        gate.stop()


def main():
    """probe.py OUT [SCENARIO ...]: writes the results to OUT as JSON."""
    out, names = sys.argv[1], sys.argv[2:] or list(SCENARIOS)
    results = {name: run(name, SCENARIOS[name]) for name in names}
    with open(out, 'w') as handle:
        json.dump(results, handle)


main()
