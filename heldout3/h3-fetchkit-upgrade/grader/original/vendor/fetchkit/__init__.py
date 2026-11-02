"""fetchkit: a small HTTP client for JSON APIs, with retries."""

from fetchkit.client import Client, Response
from fetchkit.errors import ConnectionFailed, FetchError, HTTPError, Timeout

__version__ = '1.6.2'
__all__ = ['Client', 'Response', 'FetchError', 'HTTPError', 'ConnectionFailed', 'Timeout']
