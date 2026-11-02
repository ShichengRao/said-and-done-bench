"""Timestamp parsing."""

import datetime as _dt
import re

__all__ = ['LOCAL_FORMATS', 'ParseError', 'parse', 'parse_local', 'parse_offset']

#: Local date and time layouts parse_local() accepts, tried in order.
LOCAL_FORMATS = (
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M',
    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
)

_OFFSET = re.compile(r'(?:UTC|GMT)?(?P<sign>[+-])(?P<hours>\d{1,2})(?::?(?P<minutes>\d{2}))?')
_TRAILING_OFFSET = re.compile(r'\s*(Z|UTC|GMT|(?:UTC|GMT)?[+-]\d{1,2}(?::?\d{2})?)$')


class ParseError(ValueError):
    """The text isn't a timestamp, offset, or zone rule chronoparse understands."""


def parse_local(text):
    """A naive local datetime from text in one of LOCAL_FORMATS."""
    text = text.strip()
    for layout in LOCAL_FORMATS:
        try:
            return _dt.datetime.strptime(text, layout)
        except ValueError:
            continue
    raise ParseError(f'not a timestamp chronoparse understands: {text!r}')


def parse_offset(text):
    """A UTC offset in minutes east of UTC: '+05:30' -> 330, '-0400' -> -240, 'Z' -> 0."""
    text = text.strip()
    if text.upper() in ('Z', 'UTC', 'GMT'):
        return 0
    match = _OFFSET.fullmatch(text)
    if match is None:
        raise ParseError(f'not a UTC offset: {text!r}')
    sign = -1 if match.group('sign') == '-' else 1
    return sign * (int(match.group('hours')) * 60 + int(match.group('minutes') or 0))


def parse(text):
    """An aware UTC datetime from a local timestamp followed by its UTC offset ('2026-09-14 23:45 +01:00')."""
    text = text.strip()
    match = _TRAILING_OFFSET.search(text)
    if match is None or ':' not in text[:match.start()]:
        raise ParseError(f'no UTC offset in {text!r}; use a Zone for local times')
    local = parse_local(text[:match.start()])
    return (local - _dt.timedelta(minutes=parse_offset(match.group(1)))).replace(tzinfo=_dt.timezone.utc)
