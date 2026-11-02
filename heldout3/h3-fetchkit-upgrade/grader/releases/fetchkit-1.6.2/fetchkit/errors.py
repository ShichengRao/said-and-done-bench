"""What can go wrong with a request."""


class FetchError(Exception):
    """Base class for fetchkit's errors."""


class ConnectionFailed(FetchError):
    """The server couldn't be reached, or the connection broke."""


class Timeout(FetchError):
    """The server didn't answer in time."""


class HTTPError(FetchError):
    """The server answered with an error status."""

    def __init__(self, status, body=b''):
        super().__init__(f'HTTP {status}')
        self.status = status
        self.body = body
