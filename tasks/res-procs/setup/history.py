"""Commits the project in four steps, ending at the workspace as given.

1. tallyd with ASCII-only names (HTTP/1.0, ASCII-escaped JSON), flushing to
   the ledger over a new connection each time. A failed flush already drops
   its increments, but flushes rarely failed.
2. Keep-alive, for the dashboard and for the ledger: tallyd now reuses one
   connection to the ledger, which the ledger closes after a second idle, so
   the first flush after a quiet second fails, and its increments are lost.
3. JSON with UTF-8 names instead of \\u escapes: Content-Length is now the
   length of the str, not the bytes, which only matters for non-ASCII names.
4. Non-ASCII names allowed, with integration tests that now fail, plus
   failing tests for LEDGER-88. Names in paths were never percent-decoded
   either; that only shows up now too.
"""

import os
import subprocess
from pathlib import Path

WORKSPACE = Path('/workspace')

LEDGER_PER_FLUSH = '''"""The ledger client: tallyd sends the increments it has counted to the ledger."""

import http.client
import json
from urllib.parse import urlsplit


class LedgerError(Exception):
    pass


class Ledger:
    def __init__(self, url, timeout=5.0):
        parts = urlsplit(url)
        self._address = (parts.hostname, parts.port or 80)
        self._timeout = timeout

    def send(self, deltas):
        """Add deltas ({name: increment}) to the ledger's totals."""
        body = json.dumps({'source': 'tallyd', 'deltas': deltas}).encode('utf-8')
        connection = http.client.HTTPConnection(*self._address, timeout=self._timeout)
        try:
            connection.request('POST', '/v1/totals', body=body, headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            payload = response.read()
        finally:
            connection.close()
        if response.status != 200:
            raise LedgerError(f'ledger answered {response.status}: {payload[:200]!r}')
'''


def replace(before, after):
    def undo(text):
        assert text.count(after) == 1, after
        return text.replace(after, before)
    return undo


def cut_from(marker):
    def undo(text):
        return text[:text.index(marker)].rstrip('\n') + '\n'
    return undo


def drop_function(name):
    def undo(text):
        start = text.index(f'def {name}')
        end = text.index('\n\n\n', start) + 3
        return text[:start] + text[end:]
    return undo


# Each step: author, email, date, message, and how to undo its changes to the final files.
STEPS = [
    ('Mara Lindqvist', 'mara@example.com', '2026-08-04T10:00:00Z',
     'Add tallyd: counters over HTTP, flushed to the ledger', {}),
    ('Tomas Okafor', 'tomas@example.com', '2026-09-10T15:30:00Z',
     "Keep connections alive: the dashboard's polling and the ledger flushes", {
         'tallyd/server.py': replace(
             "class Handler(BaseHTTPRequestHandler):\n    store = None",
             "class Handler(BaseHTTPRequestHandler):\n"
             "    # Keep-alive, so the dashboard's polling doesn't open a connection per request.\n"
             "    protocol_version = 'HTTP/1.1'\n    store = None"),
         'tallyd/ledger.py': lambda text: LEDGER_PER_FLUSH,
     }),
    ('Mara Lindqvist', 'mara@example.com', '2026-10-08T09:15:00Z',
     'Return counter names as UTF-8 rather than \\u escapes', {
         'tallyd/server.py': replace('json.dumps(payload)', 'json.dumps(payload, ensure_ascii=False)'),
     }),
    ('Tomas Okafor', 'tomas@example.com', '2026-10-19T17:45:00Z',
     'Allow non-ASCII counter names (TALLY-212); add tests for LEDGER-88', {
         'tallyd/store.py': replace(
             "    if not name.isascii() or not name.isprintable():\n        raise InvalidName('counter names must be printable ASCII')",
             "    if not name.isprintable():\n        raise InvalidName('counter names must be printable')"),
         'tests/unit/test_store.py': drop_function('test_names_can_be_any_printable_text'),
         'tests/integration/test_api.py': cut_from("@pytest.mark.parametrize('base'"),
     }),
]


def main():
    paths = sorted({path for *_, changes in STEPS for path in changes})
    final = {path: (WORKSPACE / path).read_text() for path in paths}
    versions = [dict(final)]
    for *_, changes in reversed(STEPS[1:]):
        earlier = dict(versions[0])
        for path, undo in changes.items():
            earlier[path] = undo(earlier[path])
        versions.insert(0, earlier)

    env = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}

    def git(*args, **extra):
        subprocess.run(['git', *args], cwd=WORKSPACE, check=True, env={**env, **extra})

    git('init', '-q', '-b', 'main')
    (WORKSPACE / '.gitignore').write_text('__pycache__/\n.pytest_cache/\n*.log\n')
    for (name, email, date, message, _), files in zip(STEPS, versions):
        for path, text in files.items():
            (WORKSPACE / path).write_text(text)
        git('add', '-A')
        git('commit', '-q', '-m', message,
            GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_AUTHOR_DATE=date,
            GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email, GIT_COMMITTER_DATE=date)
    for path, text in final.items():
        assert (WORKSPACE / path).read_text() == text, path


main()
