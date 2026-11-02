"""The ledger client: tallyd sends the increments it has counted to the ledger."""

import http.client
import json
from urllib.parse import urlsplit


class LedgerError(Exception):
    pass


class Ledger:
    def __init__(self, url, timeout=5.0):
        parts = urlsplit(url)
        # One kept-alive connection for every flush.
        self._connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)

    def send(self, deltas):
        """Add deltas ({name: increment}) to the ledger's totals."""
        body = json.dumps({'source': 'tallyd', 'deltas': deltas}).encode('utf-8')
        self._connection.request('POST', '/v1/totals', body=body, headers={'Content-Type': 'application/json'})
        response = self._connection.getresponse()
        payload = response.read()
        if response.status != 200:
            raise LedgerError(f'ledger answered {response.status}: {payload[:200]!r}')
