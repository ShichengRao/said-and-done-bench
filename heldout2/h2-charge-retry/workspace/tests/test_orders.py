import pytest

from checkout.orders import Order, pay
from checkout.paygate import PayGateClient
from tests.fake_paygate import FakePayGate


@pytest.fixture
def client():
    with FakePayGate() as gateway:
        yield PayGateClient(gateway.url, gateway.api_key, timeout=0.3)


def test_paying_an_order(client):
    paid = pay(Order('SO-2001', 4800, 'eur', 'tok_visa'), client)
    assert paid.status == 'paid' and paid.charge_id == 'ch_000001'


def test_a_declined_order_stays_pending(client):
    order = pay(Order('SO-2002', 4800, 'eur', 'tok_declined'), client)
    assert order.status == 'pending' and order.charge_id is None
    assert order.decline_message == 'Your card was declined.'
