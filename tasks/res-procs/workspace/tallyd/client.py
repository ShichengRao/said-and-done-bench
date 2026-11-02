"""A small tallyd client. It keeps one connection open, like the dashboard does."""

import http.client
import json
from urllib.parse import quote, urlsplit


class TallyError(Exception):
    def __init__(self, status, message):
        super().__init__(f'{status}: {message}')
        self.status = status


class Client:
    def __init__(self, url='http://127.0.0.1:8765', timeout=5.0):
        parts = urlsplit(url)
        self._connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)

    def close(self):
        self._connection.close()

    def health(self):
        return self._request('GET', '/healthz')

    def get(self, name):
        return self._request('GET', f'/v1/counters/{quote(name, safe="")}')['value']

    def incr(self, name, by=1):
        return self._request('POST', f'/v1/counters/{quote(name, safe="")}/incr', {'by': by})['value']

    def batch(self, increments):
        """increments: (name, by) pairs. Returns the new values, in order."""
        body = {'increments': [{'name': name, 'by': by} for name, by in increments]}
        return [item['value'] for item in self._request('POST', '/v1/batch', body)['counters']]

    def top(self, n=10):
        return [(item['name'], item['value']) for item in self._request('GET', f'/v1/top?n={n}')['counters']]

    def flush(self):
        """Have tallyd send its increments to the ledger now; returns how many counters that covered."""
        return self._request('POST', '/v1/flush')['flushed']

    def _request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        headers = {'Content-Type': 'application/json'} if data is not None else {}
        self._connection.request(method, path, body=data, headers=headers)
        response = self._connection.getresponse()
        payload = response.read()
        if response.status >= 400:
            raise TallyError(response.status, payload.decode('utf-8', 'replace'))
        return json.loads(payload)
