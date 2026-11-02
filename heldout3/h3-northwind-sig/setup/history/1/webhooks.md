# Fernway webhooks

*Published for our business customers' developers.*

When something happens to one of your orders, we POST a JSON event to the
endpoint you gave us:

    {"created": 1741600000, "data": {...}, "id": "evt_...", "type": "order.created"}

Event types: `order.created`, `order.cancelled`, `shipment.dispatched`.
Answer with any 2xx; we retry twice if your endpoint is down or answers 5xx.

## Checking that a webhook came from us

Every request is signed with the signing secret we gave you:
`X-Signature` is `sha1=` and the hex HMAC-SHA1 of the raw request body,
keyed with your signing secret. Compute the same HMAC and compare it in
constant time. In Python:

    expected = 'sha1=' + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    ok = hmac.compare_digest(headers['X-Signature'], expected)
