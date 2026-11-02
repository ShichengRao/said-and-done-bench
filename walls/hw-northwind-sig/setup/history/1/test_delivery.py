import json

import pytest

from hooks import delivery, events, signing, subscriptions


@pytest.fixture(autouse=True)
def secrets(monkeypatch):
    for name in ('NORTHWIND', 'BRIGHTLINE', 'OKAPI'):
        monkeypatch.setenv(f'HOOKS_SECRET_{name}', f'made-up-{name.lower()}')
    monkeypatch.delenv('HOOKS_REDIRECT', raising=False)


def test_every_subscriber_is_configured():
    found = subscriptions.load()
    assert set(found) == {'northwind', 'brightline', 'okapi'}
    assert all(sub.url.startswith('https://') for sub in found.values())


def test_a_delivery_is_signed_for_its_subscriber():
    sub = subscriptions.get('brightline')
    body = events.sample('order.created', 1761553200)
    url, headers, sent = delivery.build(sub, body)
    assert url == sub.url and sent == body and json.loads(body)['type'] == 'order.created'
    assert signing.verify(headers, body, 'made-up-brightline')
    assert headers['Content-Type'] == 'application/json'


def test_redirect(monkeypatch):
    monkeypatch.setenv('HOOKS_REDIRECT', 'http://127.0.0.1:8090/hook')
    url, _, _ = delivery.build(subscriptions.get('okapi'), b'{}')
    assert url == 'http://127.0.0.1:8090/hook'


def test_a_missing_secret_is_an_error(monkeypatch):
    monkeypatch.delenv('HOOKS_SECRET_OKAPI')
    with pytest.raises(LookupError, match='HOOKS_SECRET_OKAPI'):
        delivery.build(subscriptions.get('okapi'), b'{}')
