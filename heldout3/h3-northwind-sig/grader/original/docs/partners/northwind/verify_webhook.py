"""Northwind Logistics: checks the signature on incoming Fernway webhooks.

In production since April 2025 (fernway-inbound service).
"""

import hashlib
import hmac


def verify(headers, body, secret):
    """True if the request really came from Fernway.

    headers: the request's headers (case-insensitive), body: the raw body
    (bytes), secret: the signing secret Fernway gave us.
    """
    signature = headers.get('X-Signature', '')
    expected = 'sha1=' + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(signature, expected)
