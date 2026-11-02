"""The grader's own POSIX TZ zones (Mm.w.d rules), written independently of chronoparse.

Used to generate the feed data and to check the agent's times. Same rule
format as vendor/chronoparse/zones.py: offsets are hours west of UTC, the
daylight offset defaults to one hour ahead, transitions default to 02:00
local time in the offset in effect before them.
"""

import calendar
import datetime as dt
import re

_NAME = r'[A-Za-z]{3,}|<[A-Za-z0-9+-]{3,}>'
_OFFSET = r'[+-]?\d{1,2}(?::\d{2}){0,2}'
_RULE = r'M(\d{1,2})\.(\d)\.(\d)(?:/(' + _OFFSET + r'))?'
_SPEC = re.compile(rf'({_NAME})({_OFFSET})(?:({_NAME})({_OFFSET})?,{_RULE},{_RULE})?')
UTC = dt.timezone.utc


def _duration(text):
    sign = -1 if text.startswith('-') else 1
    hours, minutes, seconds = ([int(part) for part in text.lstrip('+-').split(':')] + [0, 0])[:3]
    return sign * dt.timedelta(hours=hours, minutes=minutes, seconds=seconds)


def rule_day(year, month, week, weekday):
    """Day `weekday` (0 = Sunday) of week `week` (5 = the last) of the month."""
    python_weekday = (weekday - 1) % 7  # Monday = 0
    days = [day for day in range(1, calendar.monthrange(year, month)[1] + 1)
            if dt.date(year, month, day).weekday() == python_weekday]
    return dt.date(year, month, days[-1] if week == 5 else days[week - 1])


class RefZone:
    def __init__(self, spec):
        parts = _SPEC.fullmatch(spec).groups()
        self.std_name, self.std = parts[0].strip('<>'), -_duration(parts[1])
        self.dst_name = parts[2].strip('<>') if parts[2] else None
        self.dst = -_duration(parts[3]) if parts[3] else self.std + dt.timedelta(hours=1)
        self.rules = None
        if self.dst_name:
            self.rules = [(int(parts[4]), int(parts[5]), int(parts[6]), _duration(parts[7]) if parts[7] else dt.timedelta(hours=2)),
                          (int(parts[8]), int(parts[9]), int(parts[10]), _duration(parts[11]) if parts[11] else dt.timedelta(hours=2))]

    def changes(self, year):
        """(naive UTC instant, offset after, name after) for the year's two transitions."""
        if not self.rules:
            return []
        (sm, sw, sd, st), (em, ew, ed, et) = self.rules
        start = dt.datetime.combine(rule_day(year, sm, sw, sd), dt.time()) + st - self.std
        end = dt.datetime.combine(rule_day(year, em, ew, ed), dt.time()) + et - self.dst
        return sorted([(start, self.dst, self.dst_name), (end, self.std, self.std_name)])

    def state(self, utc):
        if utc.tzinfo is not None:
            utc = utc.astimezone(UTC).replace(tzinfo=None)
        current = (self.std, self.std_name)
        for instant, offset, name in self.changes(utc.year - 1) + self.changes(utc.year):
            if instant <= utc:
                current = (offset, name)
        return current

    def to_local(self, utc):
        naive = utc.astimezone(UTC).replace(tzinfo=None)
        return naive + self.state(naive)[0]

    def abbreviation(self, utc):
        return self.state(utc)[1]

    def to_utc(self, local, fold=0):
        candidates = sorted({local - offset for offset in (self.std, self.dst) if self.state(local - offset)[0] == offset})
        if not candidates:
            raise ValueError(f'{local} is skipped in this zone')
        return candidates[min(fold, len(candidates) - 1)].replace(tzinfo=UTC)
