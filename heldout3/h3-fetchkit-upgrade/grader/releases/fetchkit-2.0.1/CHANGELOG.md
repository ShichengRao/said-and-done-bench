# Changelog

## 2.0.1 (2026-09-30)

- Fixed: a failed attempt left its connection open, so every retried
  request leaked a socket (#212). The connection is now closed whatever
  happens. 1.x has the same leak and won't get the fix.

## 2.0.0 (2026-08-18)

fetchkit 2 lines the client up with the rest of the toolkit. Upgrading from
1.x:

- **Breaking:** `timeout` and `backoff` are in milliseconds now, like every
  other duration in the toolkit. In 1.x they were seconds.
- **Breaking:** `post_json(path, payload)` is gone; use
  `post(path, json=payload)`. `Client()`'s options and the request methods'
  options are keyword-only.
- **Deprecated:** `retries` (retries after the first attempt). Use
  `max_attempts`, the number of attempts in all: `retries=2` is
  `max_attempts=3`. `retries` still works and warns; it goes in 3.0.
- New: `Client.close()`, and a client is a context manager.
- New: `put()` and `delete()`.
- Python 3.10 or later.

## 1.6.2 (2026-02-02)

- Fixed: `HTTPError` keeps the answer's body, so callers can read an API's
  error message.

## 1.6.1 (2025-11-20)

- Fixed: `FakeTransport` records each attempt's headers as sent.

## 1.6.0 (2025-09-08)

- New: `Client(headers=...)`, headers sent with every request.
