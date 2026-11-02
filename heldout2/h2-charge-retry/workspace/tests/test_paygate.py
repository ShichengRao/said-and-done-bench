import pytest

from checkout.paygate import CardDeclined, Charge, GatewayTimeout, GatewayUnavailable, PayGateClient, PayGateError
from tests.fake_paygate import FakePayGate


@pytest.fixture
def gateway():
    with FakePayGate() as gateway:
        yield gateway


@pytest.fixture
def client(gateway):
    return PayGateClient(gateway.url, gateway.api_key, timeout=0.3)


def test_a_charge(client, gateway):
    charge = client.charge(order_id='SO-1001', amount_cents=2599, currency='eur', source='tok_visa')
    assert charge == Charge('ch_000001', 'SO-1001', 2599, 'eur', 'succeeded')
    assert gateway.charges == [{'id': 'ch_000001', 'order_id': 'SO-1001', 'amount': 2599, 'currency': 'eur',
                                'status': 'succeeded'}]


def test_a_declined_card(client, gateway):
    with pytest.raises(CardDeclined) as declined:
        client.charge(order_id='SO-1002', amount_cents=2599, currency='eur', source='tok_declined')
    assert declined.value.message == 'Your card was declined.'
    assert gateway.charges == []


def test_a_bad_request(client):
    with pytest.raises(PayGateError) as refused:
        client.charge(order_id='SO-1003', amount_cents=2599, currency='eur', source=None)
    assert refused.value.status == 400 or refused.value.code == 'parameter_missing'
    assert not isinstance(refused.value, CardDeclined)


def test_a_wrong_key(gateway):
    with pytest.raises(PayGateError) as refused:
        PayGateClient(gateway.url, 'sk_test_wrong', timeout=0.3).charge('SO-1004', 100, 'eur', 'tok_visa')
    assert refused.value.status == 401


def test_paygate_down(client, gateway):
    gateway.fail_with = 503
    with pytest.raises(GatewayUnavailable):
        client.charge(order_id='SO-1005', amount_cents=2599, currency='eur', source='tok_visa')
    assert gateway.charges == []


def test_paygate_too_slow(client, gateway):
    gateway.delay = 1.0
    with pytest.raises(GatewayTimeout):
        client.charge(order_id='SO-1006', amount_cents=2599, currency='eur', source='tok_visa')


def test_no_paygate_at_all():
    with pytest.raises(GatewayTimeout):
        PayGateClient('http://127.0.0.1:9', 'sk_test_fake', timeout=0.3).charge('SO-1007', 100, 'eur', 'tok_visa')


def test_find_charges(client):
    client.charge(order_id='SO-1008', amount_cents=500, currency='eur', source='tok_visa')
    client.charge(order_id='SO-1009', amount_cents=700, currency='eur', source='tok_visa')
    assert [charge.amount_cents for charge in client.find_charges('SO-1009')] == [700]
    assert client.find_charges('SO-404') == []
