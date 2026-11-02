"""The HTTP client notify uses for the provider."""

import fetchkit

from notify import settings


def make_client(transport=None, sleep=None):
    """A client for the provider's API, set up from notify.settings.

    `transport` and `sleep` are for tests (fetchkit.testing.FakeTransport, no waiting).
    """
    return fetchkit.Client(
        settings.PROVIDER_URL,
        timeout=settings.HTTP_TIMEOUT,
        max_attempts=settings.HTTP_RETRIES + 1,
        backoff=settings.HTTP_BACKOFF,
        transport=transport,
        sleep=sleep,
        headers={'Authorization': f'Bearer {settings.PROVIDER_TOKEN}', 'User-Agent': 'fernway-notify'},
    )
