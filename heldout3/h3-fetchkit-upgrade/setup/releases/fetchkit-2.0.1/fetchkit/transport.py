"""Sending one HTTP request over a fresh connection."""

import http.client
import socket
from urllib.parse import urlsplit

from fetchkit.errors import ConnectionFailed, Timeout


class HTTPTransport:
    """One attempt at a request: send it, read the whole answer.

    send() returns (status, headers, body) or raises Timeout or ConnectionFailed.
    `timeout` is in seconds (the client converts its milliseconds).
    """

    def send(self, method, url, headers, body, timeout):
        parts = urlsplit(url)
        factory = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
        conn = factory(parts.hostname, parts.port, timeout=timeout)
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            data = response.read()
        except socket.timeout as error:
            raise Timeout(str(error) or 'timed out') from error
        except OSError as error:
            raise ConnectionFailed(str(error)) from error
        finally:
            conn.close()
        return response.status, dict(response.getheaders()), data
