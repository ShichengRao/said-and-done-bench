"""Keeping credentials out of anything people see (SECURITY.md)."""

import re
from urllib.parse import urlsplit, urlunsplit

MASK = '********'
_SECRET_NAME = re.compile(r'(?:^|_)(?:password|passwd|secret|token|api_key|private_key)$', re.IGNORECASE)


def is_secret_key(name):
    """Whether a setting with this name (the key, e.g. "api_token") holds a credential."""
    return bool(_SECRET_NAME.search(name))


def mask_url(url):
    """The URL with any password in it masked: postgresql://relay:********@db:5432/relay."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.password is None:
        return url
    host = parts.hostname or ''
    if parts.port is not None:
        host += f':{parts.port}'
    return urlunsplit(parts._replace(netloc=f'{parts.username}:{MASK}@{host}'))
