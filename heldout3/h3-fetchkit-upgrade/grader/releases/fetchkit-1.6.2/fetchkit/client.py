"""The client: requests against one base URL, retried when it makes sense."""

import json as jsonlib
import time

from fetchkit.errors import ConnectionFailed, HTTPError, Timeout
from fetchkit.transport import HTTPTransport


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return jsonlib.loads(self.body or b'null')


class Client:
    """A client for one API.

    base_url   where the API lives, e.g. "https://api.example.com"
    timeout    seconds to wait for each attempt before giving up on it
    retries    how many times to retry a failed attempt (a connection error,
               a timeout, or a 5xx answer) after the first one
    backoff    seconds to wait before the first retry; doubled before each
               one after that
    transport  what sends each attempt (default: HTTPTransport)
    sleep      what waits between attempts (default: time.sleep)
    headers    headers sent with every request
    """

    def __init__(self, base_url, timeout=10.0, retries=2, backoff=0.5, transport=None, sleep=None, headers=None):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.transport = transport or HTTPTransport()
        self.sleep = sleep or time.sleep
        self.headers = dict(headers or {})

    def request(self, method, path, body=None, headers=None):
        url = self.base_url + '/' + path.lstrip('/')
        sent = {**self.headers, **(headers or {})}
        attempts = self.retries + 1
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                status, answer_headers, data = self.transport.send(method, url, sent, body, self.timeout)
            except (ConnectionFailed, Timeout):
                if last:
                    raise
                self.sleep(self.backoff * 2 ** attempt)
                continue
            if status >= 500 and not last:
                self.sleep(self.backoff * 2 ** attempt)
                continue
            if status >= 400:
                raise HTTPError(status, data)
            return Response(status, answer_headers, data)

    def get(self, path, headers=None):
        return self.request('GET', path, headers=headers)

    def post(self, path, data=None, headers=None):
        return self.request('POST', path, body=data, headers=headers)

    def post_json(self, path, payload, headers=None):
        """POST `payload` as JSON."""
        return self.post(path, jsonlib.dumps(payload).encode(),
                         headers={'Content-Type': 'application/json', **(headers or {})})
