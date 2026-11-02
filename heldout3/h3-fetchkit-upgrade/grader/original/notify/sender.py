"""Sending one text message."""

import fetchkit

from notify import settings
from notify.client import make_client


class SendFailed(Exception):
    """The provider didn't take the message."""


def send(to, text, client=None):
    """Send `text` to the phone number `to`; returns the provider's message id.

    Failed attempts are retried by the client (see notify.settings); a
    message the provider rejects (4xx) isn't retried.
    """
    client = client or make_client()
    payload = {'to': to, 'text': text, 'sender': settings.SENDER_NAME}
    try:
        answer = client.post_json('/messages', payload)
    except fetchkit.HTTPError as error:
        try:
            reason = fetchkit.Response(error.status, {}, error.body).json().get('error')
        except ValueError:
            reason = None
        raise SendFailed(reason or f'the provider answered {error.status}') from error
    except fetchkit.FetchError as error:
        raise SendFailed(f'no answer from the provider: {error}') from error
    return answer.json()['id']
