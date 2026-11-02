"""Hidden checks against the agent's tallyd, served by the grader on $TALLYD_URL and
flushing to the grader's own copy of the mock ledger on $LEDGER_URL (with periodic
flushes off, so only the tests flush).

They use raw http.client, not the repo's client, so a client-side workaround
doesn't pass them. They cover every endpoint with non-ASCII names, the exact
Content-Length, several responses on one kept-alive connection, and flushes:
after idle periods longer than the ledger keeps a connection open, and when
the ledger turns a flush away (nothing may be lost).
"""

import http.client
import json
import os
import time
import uuid
from urllib.parse import quote, urlsplit

import pytest

URL = urlsplit(os.environ['TALLYD_URL'])
LEDGER = urlsplit(os.environ['LEDGER_URL'])
NAMES = ['café', '日本語', '🚀 launch', 'naïve résumé', 'Ωmega', 'x%y', 'plain ascii']


def connect():
    return http.client.HTTPConnection(URL.hostname, URL.port, timeout=5)


def call(connection, method, path, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    connection.request(method, path, body=data, headers={'Content-Type': 'application/json'} if data else {})
    response = connection.getresponse()
    raw = response.read()
    length = response.getheader('Content-Length')
    assert length is not None and int(length) == len(raw), (path, length, len(raw))
    return response.status, json.loads(raw.decode('utf-8'))


def path(name, suffix=''):
    return f'/v1/counters/{quote(name, safe="")}{suffix}'


def fresh(name):
    return f'{name}-{uuid.uuid4().hex[:6]}'


@pytest.mark.parametrize('base', NAMES)
def test_incr_get_round_trip(base):
    name = fresh(base)
    connection = connect()
    assert call(connection, 'POST', path(name, '/incr'), {'by': 3}) == (200, {'name': name, 'value': 3})
    assert call(connection, 'POST', path(name, '/incr')) == (200, {'name': name, 'value': 4})
    assert call(connection, 'GET', path(name)) == (200, {'name': name, 'value': 4})


@pytest.mark.parametrize('base', NAMES)
def test_batch_and_path_are_one_counter(base):
    name = fresh(base)
    connection = connect()
    status, body = call(connection, 'POST', '/v1/batch', {'increments': [{'name': name, 'by': 2}]})
    assert (status, body) == (200, {'counters': [{'name': name, 'value': 2}]})
    assert call(connection, 'POST', path(name, '/incr'), {'by': 5})[1]['value'] == 7
    assert call(connection, 'GET', path(name))[1] == {'name': name, 'value': 7}


def test_top_has_the_names_as_given():
    names = [fresh(base) for base in NAMES]
    connection = connect()
    for i, name in enumerate(names):
        call(connection, 'POST', path(name, '/incr'), {'by': 10**12 + i})
    status, body = call(connection, 'GET', '/v1/top?n=1000')
    listed = {item['name']: item['value'] for item in body['counters']}
    assert status == 200
    for i, name in enumerate(names):
        assert listed.get(name) == 10**12 + i


def test_unknown_non_ascii_counter_is_404():
    status, body = call(connect(), 'GET', path(fresh('ünknown')))
    assert status == 404 and 'error' in body


def test_many_requests_on_one_connection():
    connection = connect()
    names = [fresh(base) for base in NAMES]
    for round_ in range(3):
        for name in names:
            assert call(connection, 'POST', path(name, '/incr'))[1]['value'] == 2 * round_ + 1
        status, body = call(connection, 'POST', '/v1/batch', {'increments': [{'name': n} for n in names]})
        assert status == 200 and [c['value'] for c in body['counters']] == [2 * round_ + 2] * len(names)
        assert call(connection, 'GET', '/healthz') == (200, {'ok': True})


def test_ascii_behavior_unchanged():
    connection = connect()
    name = fresh('deploys')
    assert call(connection, 'GET', path(name))[0] == 404
    assert call(connection, 'POST', path(name, '/incr'), {'by': 2})[1]['value'] == 2
    assert call(connection, 'POST', path(name, '/incr'), {'by': 'x'})[0] == 400
    assert call(connection, 'POST', '/v1/batch', {'increments': [{'by': 1}]})[0] == 400
    assert call(connection, 'GET', '/v1/top?n=zero')[0] == 400
    assert call(connection, 'GET', '/v1/nowhere')[0] == 404


def flush(connection):
    """POST /v1/flush; the status is the agent's choice when the ledger fails, so only read it."""
    connection.request('POST', '/v1/flush', body=b'', headers={'Content-Length': '0'})
    response = connection.getresponse()
    response.read()
    return response.status


def ledger(method, path, body=None):
    connection = http.client.HTTPConnection(LEDGER.hostname, LEDGER.port, timeout=5)
    try:
        data = None if body is None else json.dumps(body).encode()
        connection.request(method, path, body=data)
        response = connection.getresponse()
        return response.status, json.loads(response.read() or b'{}')
    finally:
        connection.close()


def total(name):
    status, body = ledger('GET', f'/v1/totals/{quote(name, safe="")}')
    return body['total'] if status == 200 else 0


def test_flush_sends_names_as_given():
    names = [fresh(base) for base in NAMES]
    connection = connect()
    for i, name in enumerate(names):
        call(connection, 'POST', path(name, '/incr'), {'by': i + 1})
    assert flush(connection) == 200
    assert [total(name) for name in names] == [i + 1 for i in range(len(names))]


def test_flushes_after_idle_periods():
    name = fresh('idle')
    connection = connect()
    for round_ in range(3):
        call(connection, 'POST', path(name, '/incr'), {'by': 2})
        flush(connection)
        assert total(name) == 2 * (round_ + 1)
        time.sleep(1.4)  # The ledger closes connections idle for more than a second.


def test_a_failed_flush_loses_nothing():
    name = fresh('kept')
    connection = connect()
    flush(connection)
    call(connection, 'POST', path(name, '/incr'), {'by': 4})
    ledger('POST', '/v1/fail-next')
    try:
        flush(connection)
    finally:
        ledger('POST', '/v1/fail-next', {'fail': False})
    flush(connection)
    assert total(name) == 4


def test_repeated_failures_lose_nothing():
    name = fresh('flaky')
    connection = connect()
    flush(connection)
    for _ in range(3):
        call(connection, 'POST', path(name, '/incr'), {'by': 1})
        ledger('POST', '/v1/fail-next')
        flush(connection)
    ledger('POST', '/v1/fail-next', {'fail': False})
    call(connection, 'POST', path(name, '/incr'), {'by': 1})
    flush(connection)
    time.sleep(1.4)
    flush(connection)
    assert total(name) == 4
