# fetchkit

A small HTTP client for JSON APIs, with retries.

    from fetchkit import Client

    client = Client('https://api.example.com', timeout=5.0, retries=3)
    order = client.get('/orders/42').json()
    client.post_json('/orders', {'sku': 'A-1', 'qty': 2})

Failed attempts (a connection error, a timeout, or a 5xx answer) are retried
after a wait that doubles each time. A 4xx answer raises `HTTPError` at once.

For tests, `fetchkit.testing.FakeTransport` answers from a script and
records every attempt.
