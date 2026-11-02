import json

import pytest

import notify  # noqa: F401  (puts vendor/ on the path)
from fetchkit import ConnectionFailed, Timeout
from fetchkit.testing import FakeTransport

from notify.client import make_client
from notify.sender import SendFailed, send


def client_for(answers):
    transport = FakeTransport(answers)
    return make_client(transport=transport, sleep=lambda seconds: None), transport


def test_send_posts_the_message():
    client, transport = client_for([(202, {'id': 'msg_1', 'status': 'queued'})])
    assert send('+4915112345678', 'Your order has shipped', client=client) == 'msg_1'
    [request] = transport.requests
    assert request['method'] == 'POST' and request['url'].endswith('/messages')
    assert json.loads(request['body']) == {'to': '+4915112345678', 'text': 'Your order has shipped',
                                           'sender': 'Fernway'}
    assert request['headers']['Authorization'].startswith('Bearer ')


def test_a_server_error_is_retried():
    client, transport = client_for([(503, {'error': 'busy'}), (202, {'id': 'msg_2'})])
    assert send('+4915112345678', 'hi', client=client) == 'msg_2'
    assert len(transport.requests) == 2


def test_a_timeout_or_a_dropped_connection_is_retried():
    client, transport = client_for([Timeout('timed out'), ConnectionFailed('reset'), (202, {'id': 'msg_3'})])
    assert send('+4915112345678', 'hi', client=client) == 'msg_3'


def test_a_rejected_message_is_not_retried():
    client, transport = client_for([(400, {'error': 'invalid phone number'})])
    with pytest.raises(SendFailed, match='invalid phone number'):
        send('015112345678', 'hi', client=client)
    assert len(transport.requests) == 1


def test_giving_up_says_why():
    client, _ = client_for([(503, {})] * 5)
    with pytest.raises(SendFailed, match='503'):
        send('+4915112345678', 'hi', client=client)
