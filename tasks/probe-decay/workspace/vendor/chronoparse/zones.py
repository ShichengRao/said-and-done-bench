"""Time zones from POSIX TZ rules, as embedded devices store them.

    std offset [dst [offset] ,start[/time],end[/time]]

    EST5EDT,M3.2.0,M11.1.0       UTC-5, daylight time UTC-4 from the second
                                 Sunday in March to the first in November
    NST3:30NDT,M3.2.0,M11.1.0    UTC-3:30 and UTC-2:30
    GMT0BST,M3.5.0/1,M10.5.0     daylight time from 01:00 on the last Sunday
                                 in March to 02:00 on the last in October
    IST-5:30                     UTC+5:30 all year

Offsets are hours west of UTC (EST5 is five hours behind it), optionally
with minutes and seconds. The daylight offset defaults to one hour ahead of
standard time. Rule dates are Mm.w.d: day d (0 = Sunday) of week w (1 to 5,
where 5 means the last) of month m. A transition happens at that local
wall-clock time (02:00 unless given) in the offset in effect before it.
Transitions are worked out for 1970 to 2037.
"""

import bisect
import datetime as _dt
import functools
import re
from typing import NamedTuple

from chronoparse.parser import ParseError

__all__ = ['NonexistentTimeError', 'Rule', 'Zone', 'zone']

FIRST_YEAR, LAST_YEAR = 1970, 2037
_UTC = _dt.timezone.utc
_NAME = r'[A-Za-z]{3,}|<[A-Za-z0-9+-]{3,}>'
_OFFSET = r'[+-]?\d{1,2}(?::\d{2}){0,2}'
_RULE = r'M\d{1,2}\.\d\.\d(?:/' + _OFFSET + ')?'
_SPEC = re.compile(rf'(?P<std>{_NAME})(?P<std_offset>{_OFFSET})'
                   rf'(?:(?P<dst>{_NAME})(?P<dst_offset>{_OFFSET})?,(?P<start>{_RULE}),(?P<end>{_RULE}))?')


class NonexistentTimeError(ValueError):
    """A local time that was skipped when the clocks went forward."""


class Rule(NamedTuple):
    month: int
    week: int  # 1 to 5; 5 is the last such weekday of the month
    weekday: int  # 0 = Sunday
    time: _dt.timedelta  # local wall-clock time of the change


def _duration(text):
    sign = -1 if text.startswith('-') else 1
    parts = [int(part) for part in text.lstrip('+-').split(':')] + [0, 0]
    return sign * _dt.timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])


def _rule(text):
    date, _, time = text.partition('/')
    month, week, weekday = (int(part) for part in date[1:].split('.'))
    if not (1 <= month <= 12 and 1 <= week <= 5 and 0 <= weekday <= 6):
        raise ParseError(f'not an Mm.w.d rule: {text!r}')
    return Rule(month, week, weekday, _duration(time) if time else _dt.timedelta(hours=2))


class Zone:
    """A time zone from a POSIX TZ rule. See the module docstring for the format."""

    def __init__(self, spec):
        match = _SPEC.fullmatch(spec.strip())
        if match is None:
            raise ParseError(f'not a POSIX TZ rule chronoparse understands: {spec!r}')
        self.spec = spec.strip()
        self.std_name = match.group('std').strip('<>')
        self.std_offset = -_duration(match.group('std_offset'))  # east of UTC
        self.dst_name = match.group('dst').strip('<>') if match.group('dst') else None
        self.dst_offset = (-_duration(match.group('dst_offset')) if match.group('dst_offset')
                           else self.std_offset + _dt.timedelta(hours=1))
        self.start_rule = _rule(match.group('start')) if self.dst_name else None
        self.end_rule = _rule(match.group('end')) if self.dst_name else None
        changes = []  # (UTC instant, offset from then on, name from then on)
        if self.dst_name:
            for year in range(FIRST_YEAR, LAST_YEAR + 1):
                for rule, before, after, name in (
                        (self.start_rule, self.std_offset, self.dst_offset, self.dst_name),
                        (self.end_rule, self.dst_offset, self.std_offset, self.std_name)):
                    first = _dt.date(year, rule.month, 1)
                    # Days from the 1st to the month's first such weekday.
                    ahead = (rule.weekday - (first.weekday() + 1) % 7) % 7 or 7
                    day = first + _dt.timedelta(days=ahead + 7 * (rule.week - 1))
                    while day.month != rule.month:
                        day -= _dt.timedelta(weeks=1)
                    changes.append((_dt.datetime.combine(day, _dt.time()) + rule.time - before, after, name))
            changes.sort()
        self._instants = [instant for instant, _, _ in changes]
        self._after = [(offset, name) for _, offset, name in changes]
        if changes and changes[0][1] == self.dst_offset:
            self._initial = (self.std_offset, self.std_name)
        elif changes:
            self._initial = (self.dst_offset, self.dst_name)
        else:
            self._initial = (self.std_offset, self.std_name)

    def __repr__(self):
        return f'Zone({self.spec!r})'

    def _state(self, utc):
        """(offset, name) in effect at a UTC instant (aware, or naive in UTC)."""
        if utc.tzinfo is not None:
            utc = utc.astimezone(_UTC).replace(tzinfo=None)
        index = bisect.bisect_right(self._instants, utc) - 1
        return self._after[index] if index >= 0 else self._initial

    def utcoffset_at(self, utc):
        return self._state(utc)[0]

    def abbreviation(self, utc):
        """The zone's name at a UTC instant: 'EST' or 'EDT'."""
        return self._state(utc)[1]

    def to_local(self, utc):
        """The naive local wall-clock time at a UTC instant."""
        naive = utc.astimezone(_UTC).replace(tzinfo=None) if utc.tzinfo is not None else utc
        return naive + self._state(naive)[0]

    def to_utc(self, local, fold=0):
        """The aware UTC instant for a naive local wall-clock time.

        In the hour repeated when the clocks go back, fold=0 picks its first
        occurrence (daylight time) and fold=1 the second (standard time);
        elsewhere fold makes no difference. A time skipped when the clocks go
        forward raises NonexistentTimeError.
        """
        candidates = sorted({local - offset for offset in (self.std_offset, self.dst_offset)
                             if self._state(local - offset)[0] == offset})
        if not candidates:
            raise NonexistentTimeError(f'{local} does not exist in {self.spec}')
        return candidates[min(fold, len(candidates) - 1)].replace(tzinfo=_UTC)

    def transitions(self, year):
        """The year's changes as (aware UTC instant, offset after, name after)."""
        return [(instant.replace(tzinfo=_UTC), offset, name)
                for instant, (offset, name) in zip(self._instants, self._after) if instant.year == year]


@functools.lru_cache(maxsize=None)
def zone(spec):
    """The Zone for a POSIX TZ rule, cached."""
    return Zone(spec)
