"""Webhook signatures (docs/webhooks.md, SEC-88).

A delivery carries X-Webhook-Timestamp (Unix seconds) and X-Signature-256:
"sha256=" and the hex HMAC-SHA256 of "<timestamp>.<body>", keyed with the
subscriber's signing secret.

Until October 1, 2026 it also carries the old X-Signature (HMAC-SHA1 of the
body), so subscribers can move over; SEC-88 retires it then.
"""

import hashlib
import hmac

TOLERANCE_S = 300


def signature(body, secret, timestamp):
    message = f'{timestamp}.'.encode() + body
    return 'sha256=' + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def legacy_signature(body, secret):
    """X-Signature, deprecated: goes on October 1, 2026 (SEC-88)."""
    return 'sha1=' + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()


def sign(body, secret, timestamp):
    """The headers that sign `body` for a subscriber."""
    return {'X-Webhook-Timestamp': str(timestamp), 'X-Signature-256': signature(body, secret, timestamp),
            'X-Signature': legacy_signature(body, secret)}


def verify(headers, body, secret, now):
    """What a subscriber does (docs/webhooks.md): the signature matches and isn't more than 5 minutes old."""
    try:
        timestamp = int(headers.get('X-Webhook-Timestamp', ''))
    except ValueError:
        return False
    if abs(now - timestamp) > TOLERANCE_S:
        return False
    return hmac.compare_digest(headers.get('X-Signature-256', ''), signature(body, secret, timestamp))
