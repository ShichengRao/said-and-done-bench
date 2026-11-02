# PayGate API v1: the parts we use

Copied from PayGate's API reference (developer.paygate.example/v1), October 2026.

Base URL `https://api.paygate.example`. Authenticate every request with your
secret key: `Authorization: Bearer sk_live_...`. Request and response bodies
are JSON.

## Create a charge

`POST /v1/charges`

| Field      | Type    | Description                                                    |
|------------|---------|----------------------------------------------------------------|
| `amount`   | integer | Amount in the currency's minor unit (cents for EUR).           |
| `currency` | string  | ISO 4217 code, lowercase (`eur`).                              |
| `source`   | string  | A card token from PayGate's checkout form (`tok_...`).         |
| `order_id` | string  | Your reference for the payment, up to 64 characters. Searchable. |

Optional headers: `Idempotency-Key` (see [Idempotent requests](#idempotent-requests)).

Responses:

- `201 Created`: the charge, `{"id": "ch_...", "order_id": "...", "amount": 2599, "currency": "eur", "status": "succeeded"}`.
- `402 Payment Required`: the card was declined. No charge is made.
- `400`, `401`, `404`, `409`, `422`: something is wrong with the request.
- `500`, `502`, `503`, `504`: something went wrong at PayGate.

Errors have a body like `{"error": {"code": "card_declined", "message": "Your card has insufficient funds."}}`.

## List charges

`GET /v1/charges?order_id=SO-1234` returns `{"data": [...]}`: the charges with
that `order_id`, newest first.

## Idempotent requests

PayGate supports idempotency for safely retrying requests without accidentally
performing the same operation twice. To make a `POST` idempotent, send an
`Idempotency-Key: <key>` header, where the key is a unique value you generate
(up to 255 characters; we suggest a V4 UUID).

Once PayGate has processed a request with a key, it saves the response (a
charge or a decline) and returns that same response to any later request with
the same key. A `5xx` response isn't saved, so a later request with the same
key is processed normally. If a request with the same key is still in
progress, the later request waits for it and gets its response. Keys expire
after 24 hours. Reusing a key with different parameters returns
`422 idempotency_key_reused`.

## Rate limits

100 requests per second per account. Over the limit: `429`.
