import contextlib
import time

import pytest

from tallyd.client import TallyError


def test_health(client):
    assert client.health() == {'ok': True}


def test_incr_and_get(client, unique):
    name = unique('deploys')
    assert client.incr(name) == 1
    assert client.incr(name, 2) == 3
    assert client.get(name) == 3


def test_unknown_counter(client, unique):
    with pytest.raises(TallyError) as error:
        client.get(unique('never-incremented'))
    assert error.value.status == 404


def test_batch(client, unique):
    a, b = unique('builds'), unique('tests')
    assert client.batch([(a, 2), (b, 5), (a, 1)]) == [2, 5, 3]
    assert client.get(a) == 3


def test_top(client, unique):
    name = unique('hot')
    client.incr(name, 10**9)
    assert (name, 10**9) in client.top(1000)


def test_flush_sends_increments_to_the_ledger(client, ledger, unique):
    name = unique('flushed')
    client.incr(name, 2)
    client.flush()
    assert ledger.total(name) == 2


@pytest.mark.parametrize('base', ['café', 'naïve-日本'])
def test_non_ascii_names(client, unique, base):
    name = unique(base)
    assert client.incr(name, 2) == 2
    assert client.get(name) == 2


def test_batch_and_incr_share_counters(client, unique):
    name = unique('Größe')
    assert client.incr(name) == 1
    assert client.batch([(name, 4)]) == [5]
    assert client.get(name) == 5


def test_top_shows_names_as_given(client, unique):
    name = unique('émoji-🚀')
    client.incr(name, 10**9 + 7)
    assert (name, 10**9 + 7) in client.top(1000)


# LEDGER-88: the ledger's totals come up short.

def test_flush_after_a_quiet_period(client, ledger, unique):
    name = unique('quiet')
    client.incr(name, 2)
    client.flush()
    assert ledger.total(name) == 2
    time.sleep(1.5)  # Longer than the ledger keeps an idle connection open.
    client.incr(name, 3)
    client.flush()
    assert ledger.total(name) == 5


def test_a_failed_flush_loses_nothing(client, ledger, unique):
    name = unique('kept')
    client.flush()  # Send whatever earlier tests left.
    client.incr(name, 4)
    ledger.fail_next()
    try:
        with contextlib.suppress(TallyError):
            client.flush()  # The ledger turns this one away.
        client.flush()
    finally:
        ledger.fail_next(False)  # Don't leave the next run a failure.
    assert ledger.total(name) == 4
