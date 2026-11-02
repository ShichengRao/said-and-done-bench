"""A stand-in for the provider's API, for trying notify by hand.

    python3 -m notify.devserver [--port 8025]

Then, in another shell:

    NOTIFY_PROVIDER_URL=http://127.0.0.1:8025 python3 -m notify send --to +4915112345678 --text hi

It answers POST /messages the way the provider does, taking about as long
(150 ms), and prints each message it gets. A number that doesn't start with
"+" is rejected with 400, as the provider does.
"""

import argparse
import itertools
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LATENCY_S = 0.15
_ids = itertools.count(1)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(LATENCY_S)
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if self.path.rstrip('/') != '/messages':
            return self.answer(404, {'error': 'not found'})
        try:
            message = json.loads(body)
        except ValueError:
            return self.answer(400, {'error': 'body is not JSON'})
        if not str(message.get('to', '')).startswith('+'):
            return self.answer(400, {'error': 'invalid phone number'})
        message_id = f'msg_{next(_ids):05d}'
        print(f"{message_id} to {message['to']}: {message.get('text')!r}", flush=True)
        self.answer(202, {'id': message_id, 'status': 'queued'})

    def answer(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(prog='python3 -m notify.devserver')
    parser.add_argument('--port', type=int, default=8025)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'provider stand-in on http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
