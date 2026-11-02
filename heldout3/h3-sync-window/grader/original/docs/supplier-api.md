# Halden Wholesale: Product API v3

*From Halden's integrator documentation (October 2026), the parts we use.*

Base URL: `https://api.halden-wholesale.example/v3`

Authentication: send your API key in every request as
`Authorization: Bearer <key>`.

## GET /products/{sku}

Today's price and stock level for one product.

    200 OK
    {"sku": "HW-104233", "name": "Oak serving board, large",
     "price": {"amount": "12.40", "currency": "EUR"}, "stock": 140,
     "updated_at": "2026-10-25T02:00:00+02:00"}

`404 Not Found` if the SKU doesn't exist (any more). There is no endpoint
for several products at once.

## When prices change

Prices and stock levels for the coming day are published at 02:00
(Europe/Berlin) every night. Until then the API serves the previous day's.

## Rate limits

Each API key may make at most 4 requests per second, counted over any
one-second window. A request over the limit is answered
`429 Too Many Requests` (with `Retry-After`) and is recorded against the
key; a key with more than 100 such requests in a day is suspended for 24
hours (Integration Agreement, §7.2). Every request counts, whatever its
answer.

The Enterprise plan raises the limit to 20 requests per second; talk to
your account manager.

## Errors

`5xx`: something went wrong on our side; try again a little later.
