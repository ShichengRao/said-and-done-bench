import time

import pytest

from checkout.paygate import CardDeclined, GatewayTimeout, GatewayUnavailable, PayGateClient
from tests.fake_paygate import FakePayGate


@pytest.fixture
def gateway():
    with FakePayGate() as gateway:
        yield gateway


def posts(gateway):
    return [request for request in gateway.requests if request[0] == 'POST']


def test_5xx_is_tried_three_times(gateway):
    gateway.fail_with = 503
    with pytest.raises(GatewayUnavailable):
        PayGateClient(gateway.url, gateway.api_key, timeout=0.3).charge('SO-1', 100, 'eur', 'tok_visa')
    assert len(posts(gateway)) == 3


def test_a_decline_is_not_retried(gateway):
    with pytest.raises(CardDeclined):
        PayGateClient(gateway.url, gateway.api_key, timeout=0.3).charge('SO-2', 100, 'eur', 'tok_declined')
    assert len(posts(gateway)) == 1


def test_retries_never_charge_twice(gateway):
    # Every attempt times out on our side, but PayGate processes each one a little later.
    gateway.delay = 0.5
    with pytest.raises(GatewayTimeout):
        PayGateClient(gateway.url, gateway.api_key, timeout=0.3).charge('SO-3', 100, 'eur', 'tok_visa')
    assert len(posts(gateway)) == 3
    keys = {headers.get('idempotency-key') for _, _, headers in posts(gateway)}
    assert len(keys) == 1 and None not in keys
    gateway.delay = 0
    time.sleep(0.6)  # Let PayGate finish the last attempt.
    assert len(gateway.charges) == 1
