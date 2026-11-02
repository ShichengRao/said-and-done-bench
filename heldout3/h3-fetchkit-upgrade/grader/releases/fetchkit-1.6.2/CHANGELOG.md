# Changelog

## 1.6.2 (2026-02-02)

- Fixed: `HTTPError` keeps the answer's body, so callers can read an API's
  error message.

## 1.6.1 (2025-11-20)

- Fixed: `FakeTransport` records each attempt's headers as sent.

## 1.6.0 (2025-09-08)

- New: `Client(headers=...)`, headers sent with every request.
