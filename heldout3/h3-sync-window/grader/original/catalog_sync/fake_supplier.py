"""A stand-in for Halden's product API, for trying the sync out on this machine.

    python3 -m catalog_sync.fake_supplier [--port 8099] [--latency 0.45]
    CATALOG_SUPPLIER_URL=http://127.0.0.1:8099/v3 python3 -m catalog_sync run --limit 50

Same endpoint and answers as the real API, and by default about as slow
(0.45 s a request, what the nightly logs show). Prices are made up.
"""

import argparse
import hashlib
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SKU = re.compile(r'^/v3/products/(HW-\d{6})$')


def product(sku):
    digest = int(hashlib.sha256(sku.encode()).hexdigest(), 16)
    return {'sku': sku, 'name': f'Product {sku[3:]}',
            'price': {'amount': f'{(digest % 40000) / 100 + 0.99:.2f}', 'currency': 'EUR'},
            'stock': digest % 500, 'updated_at': '2026-10-26T02:00:00+01:00'}


def handler(latency):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(latency)
            found = SKU.match(self.path)
            status, payload = (200, product(found.group(1))) if found else (404, {'error': 'unknown SKU'})
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(prog='python3 -m catalog_sync.fake_supplier')
    parser.add_argument('--port', type=int, default=8099)
    parser.add_argument('--latency', type=float, default=0.45)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.latency))
    print(f'fake supplier on http://127.0.0.1:{args.port}/v3 ({args.latency} s a request)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
