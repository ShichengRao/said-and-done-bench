"""Integration tests run against a live tallyd, the dev server (`python3 -m tallyd.dev`) by default
or the one at $TALLYD_URL, and the mock ledger it flushes to, at $LEDGER_URL."""

import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from tallyd.client import Client

ROOT = Path(__file__).resolve().parents[2]
URL = os.environ.get('TALLYD_URL', 'http://127.0.0.1:8765')
LEDGER_URL = os.environ.get('LEDGER_URL', 'http://127.0.0.1:8770')


def listening(url):
    parts = urlsplit(url)
    try:
        socket.create_connection((parts.hostname, parts.port), timeout=2).close()
        return True
    except OSError:
        return False


@pytest.fixture(scope='session')
def client():
    if not listening(URL):
        pytest.fail(f'tallyd is not running at {URL}; start it with `python3 -m tallyd.dev` (see README.md)',
                    pytrace=False)
    client = Client(URL)
    yield client
    client.close()


class MockLedger:
    def __init__(self, url):
        self.url = url.rstrip('/')

    def total(self, name):
        try:
            with urlopen(f'{self.url}/v1/totals/{quote(name, safe="")}', timeout=5) as response:
                return json.load(response)['total']
        except HTTPError as error:
            if error.code == 404:
                return 0
            raise

    def fail_next(self, fail=True):
        body = json.dumps({'fail': fail}).encode()
        urlopen(Request(f'{self.url}/v1/fail-next', data=body, method='POST'), timeout=5).close()


@pytest.fixture(scope='session')
def ledger():
    """The mock ledger. If nothing is listening at $LEDGER_URL, start one in the background and leave
    it running: the dev server flushes to it, and later test runs reuse it. Stop it with
    `python3 -m devtools.ledger_mock --stop` (see README.md)."""
    if not listening(LEDGER_URL):
        subprocess.run(
            [sys.executable, '-m', 'devtools.ledger_mock', '--daemon', '--port', str(urlsplit(LEDGER_URL).port)],
            cwd=ROOT, check=True, capture_output=True, timeout=30,
        )
    return MockLedger(LEDGER_URL)


@pytest.fixture
def unique():
    """Counter names unique to this test run, since the servers keep their counts between runs."""
    suffix = uuid.uuid4().hex[:8]
    return lambda base: f'{base}-{suffix}'
