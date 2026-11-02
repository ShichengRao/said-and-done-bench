"""How notify talks to the SMS provider (Textwise)."""

import os

PROVIDER_URL = os.environ.get('NOTIFY_PROVIDER_URL', 'https://api.textwise.example/v2')
PROVIDER_TOKEN = os.environ.get('NOTIFY_PROVIDER_TOKEN', '')
SENDER_NAME = 'Fernway'

# Textwise answers in about 150 ms, and in a few seconds when it's busy (its
# status page has had 6 s answers at peak); it asks clients to wait at least
# half a second before retrying.
HTTP_TIMEOUT = 10.0  # seconds to wait for an answer to each attempt
HTTP_RETRIES = 2     # retries after a failed attempt (a timeout, a dropped connection, or a 5xx)
HTTP_BACKOFF = 0.5   # seconds before the first retry; doubled before each one after that
