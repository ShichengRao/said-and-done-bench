# notify

Sends customers' order and delivery text messages through our SMS provider,
Textwise. The order service calls `notify.sender.send()`; there's also a
command line:

    python3 -m notify send --to +4915112345678 --text "Your order has shipped"

`notify/settings.py` has the provider's address and how long to wait for it;
`NOTIFY_PROVIDER_URL` and `NOTIFY_PROVIDER_TOKEN` override them.

## Trying it by hand

`python3 -m notify.devserver` runs a stand-in for the provider on port 8025
that answers like the real one (and about as fast). With it running:

    NOTIFY_PROVIDER_URL=http://127.0.0.1:8025 python3 -m notify send --to +4915112345678 --text hi

## Dependencies

notify uses fetchkit, an HTTP client, which we vendor: see `vendor/README.md`.

## Tests

    python3 -m pytest
