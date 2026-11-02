"""The client: requests against one base URL, retried when it makes sense."""

import json as jsonlib
import time
import warnings

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

    base_url      where the API lives, e.g. "https://api.example.com"
    timeout       milliseconds to wait for each attempt before giving up on it
    max_attempts  how many attempts to make in all, the first included, when
                  attempts fail (a connection error, a timeout, or a 5xx answer)
    backoff       milliseconds to wait before the second attempt; doubled
                  before each one after that
    transport     what sends each attempt (default: HTTPTransport)
    sleep         what waits between attempts, given seconds (default: time.sleep)
    headers       headers sent with every request
    retries       deprecated: retries after the first attempt (max_attempts - 1)

    A client is a context manager; close() releases what it holds.
    """

    def __init__(self, base_url, *, timeout=10_000, max_attempts=3, backoff=250, transport=None, sleep=None,
                 headers=None, retries=None):
        if retries is not None:
            warnings.warn('fetchkit: Client(retries=N) is deprecated and will be removed in 3.0; '
                          'use max_attempts=N + 1', DeprecationWarning, stacklevel=2)
            max_attempts = retries + 1
        if max_attempts < 1:
            raise ValueError('max_attempts must be at least 1')
        self.base_url = base_url.rstrip('/')
        self.timeout_ms = timeout
        self.max_attempts = max_attempts
        self.backoff_ms = backoff
        self.transport = transport or HTTPTransport()
        self.sleep = sleep or time.sleep
        self.headers = dict(headers or {})

    def request(self, method, path, *, json=None, data=None, headers=None):
        url = self.base_url + '/' + path.lstrip('/')
        sent = {**self.headers, **(headers or {})}
        body = data
        if json is not None:
            body = jsonlib.dumps(json).encode()
            sent.setdefault('Content-Type', 'application/json')
        for attempt in range(self.max_attempts):
            last = attempt == self.max_attempts - 1
            try:
                status, answer_headers, answer = self.transport.send(method, url, sent, body, self.timeout_ms)
            except (ConnectionFailed, Timeout):
                if last:
                    raise
                self.sleep(self.backoff_ms * 2 ** attempt)
                continue
            if status >= 500 and not last:
                self.sleep(self.backoff_ms * 2 ** attempt)
                continue
            if status >= 400:
                raise HTTPError(status, answer)
            return Response(status, answer_headers, answer)

    def get(self, path, *, headers=None):
        return self.request('GET', path, headers=headers)

    def post(self, path, *, json=None, data=None, headers=None):
        return self.request('POST', path, json=json, data=data, headers=headers)

    def put(self, path, *, json=None, data=None, headers=None):
        return self.request('PUT', path, json=json, data=data, headers=headers)

    def delete(self, path, *, headers=None):
        return self.request('DELETE', path, headers=headers)

    def close(self):
        close = getattr(self.transport, 'close', None)
        if close:
            close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
