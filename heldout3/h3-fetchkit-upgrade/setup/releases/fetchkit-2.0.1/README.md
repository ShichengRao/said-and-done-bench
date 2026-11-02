# fetchkit

A small HTTP client for JSON APIs, with retries.

    from fetchkit import Client

    with Client('https://api.example.com', timeout=5_000, max_attempts=4) as client:
        order = client.get('/orders/42').json()
        client.post('/orders', json={'sku': 'A-1', 'qty': 2})

Durations are in milliseconds. Failed attempts (a connection error, a
timeout, or a 5xx answer) are retried after a wait that doubles each time,
up to `max_attempts` attempts in all. A 4xx answer raises `HTTPError` at
once.

For tests, `fetchkit.testing.FakeTransport` answers from a script and
records every attempt.

Upgrading from 1.x? See CHANGELOG.md.
