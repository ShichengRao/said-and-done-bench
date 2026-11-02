"""A receiver for trying deliveries out: prints every request it gets.

    python3 -m hooks.receiver [--port 8090]
    HOOKS_REDIRECT=http://127.0.0.1:8090/hook python3 -m hooks send northwind
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        print(f'POST {self.path}', flush=True)
        for name, value in self.headers.items():
            print(f'{name}: {value}', flush=True)
        print(body.decode(errors='replace'), flush=True)
        print(flush=True)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(prog='python3 -m hooks.receiver')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    print(f'listening on http://127.0.0.1:{args.port}', flush=True)
    HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
