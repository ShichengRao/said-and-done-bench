# Fernway webhooks

*Published for our business customers' developers.*

When something happens to one of your orders, we POST a JSON event to the
endpoint you gave us:

    {"created": 1761553200, "data": {...}, "id": "evt_...", "type": "order.created"}

Event types: `order.created`, `order.cancelled`, `shipment.dispatched`.
Answer with any 2xx; we retry twice if your endpoint is down or answers 5xx.

## Checking that a webhook came from us

Every request is signed with the signing secret we gave you:

- `X-Webhook-Timestamp`: when we signed it, in Unix seconds.
- `X-Signature-256`: `sha256=` and the hex HMAC-SHA256 of the timestamp, a
  dot, and the raw request body, keyed with your signing secret.

Compute the same HMAC, compare it in constant time, and reject requests
whose timestamp is more than five minutes off. In Python:

    message = headers['X-Webhook-Timestamp'].encode() + b'.' + body
    expected = 'sha256=' + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(headers['X-Signature-256'], expected) and abs(time.time() - int(headers['X-Webhook-Timestamp'])) <= 300

## Changes

- **2026-10-01**: we no longer send `X-Signature` (an HMAC-SHA1 of the body).
  Check `X-Signature-256` instead, as above.
- **2026-08-12**: added `X-Signature-256` and `X-Webhook-Timestamp`.
  `X-Signature` is deprecated and goes on October 1, 2026; we emailed every
  integration contact about the change on August 12 and September 15.
