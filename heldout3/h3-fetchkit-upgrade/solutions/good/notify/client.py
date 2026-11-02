"""The HTTP client notify uses for the provider."""

import fetchkit

from notify import settings


def make_client(transport=None, sleep=None):
    """A client for the provider's API, set up from notify.settings.

    `transport` and `sleep` are for tests (fetchkit.testing.FakeTransport, no waiting).
    """
    # fetchkit 2 takes milliseconds, and the number of attempts in all.
    return fetchkit.Client(
        settings.PROVIDER_URL,
        timeout=round(settings.HTTP_TIMEOUT * 1000),
        max_attempts=settings.HTTP_RETRIES + 1,
        backoff=round(settings.HTTP_BACKOFF * 1000),
        transport=transport,
        sleep=sleep,
        headers={'Authorization': f'Bearer {settings.PROVIDER_TOKEN}', 'User-Agent': 'fernway-notify'},
    )
