"""Delivering a webhook: sign it, POST it, retry a few times if the subscriber is down.

HOOKS_REDIRECT, if set, sends every delivery to that URL instead of the
subscriber's (for trying deliveries out against hooks.receiver).
"""

import os
import time
import urllib.error
import urllib.request

from hooks import signing

ATTEMPTS = 3


def build(subscription, body):
    """(url, headers, body) for delivering `body` to a subscriber."""
    headers = {'Content-Type': 'application/json', 'User-Agent': 'fernway-hooks/2.1',
               **signing.sign(body, subscription.secret)}
    return os.environ.get('HOOKS_REDIRECT') or subscription.url, headers, body


def deliver(subscription, body, sleep=time.sleep):
    """POSTs the event; returns the subscriber's status. Raises after ATTEMPTS failures."""
    url, headers, body = build(subscription, body)
    for attempt in range(1, ATTEMPTS + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=10) as answer:
                return answer.status
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == ATTEMPTS:
                raise
        except OSError:
            if attempt == ATTEMPTS:
                raise
        sleep(2 ** attempt)
