"""Webhook signatures (docs/webhooks.md).

A delivery carries X-Signature: "sha1=" and the hex HMAC-SHA1 of the body,
keyed with the subscriber's signing secret.
"""

import hashlib
import hmac


def signature(body, secret):
    return 'sha1=' + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()


def sign(body, secret):
    """The headers that sign `body` for a subscriber."""
    return {'X-Signature': signature(body, secret)}


def verify(headers, body, secret):
    """What a subscriber does (docs/webhooks.md)."""
    return hmac.compare_digest(headers.get('X-Signature', ''), signature(body, secret))
