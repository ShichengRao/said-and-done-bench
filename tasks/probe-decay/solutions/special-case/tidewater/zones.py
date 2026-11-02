"""Station time zones.

The vendored chronoparse 0.9.2 puts a transition a week late when a month
starts on the rule's weekday: Zone counts the days to "the month's first
Sunday" with `or 7`, so when the 1st is itself a Sunday it picks the 8th.
November 1 2026 is a Sunday, so US-style rules (M11.1.0) leave daylight
time on November 8 instead of November 1, and March 2026 (M3.2.0) starts it
on the 15th instead of the 8th. vendor/ is synced from upstream, so the
correction lives here: Zone recomputes the transitions with the right dates.
Use zone() rather than chronoparse.zone() everywhere in tidewater.
"""

from __future__ import annotations

import calendar
import datetime as dt
import functools

import chronoparse
from chronoparse import zones as vendored


def rule_date(year: int, rule: chronoparse.Rule) -> dt.date:
    """Day `rule.weekday` (0 = Sunday) of week `rule.week` (5 = the last) of `rule.month`."""
    weekday = (rule.weekday - 1) % 7  # Python counts from Monday
    days = [day for day in range(1, calendar.monthrange(year, rule.month)[1] + 1)
            if dt.date(year, rule.month, day).weekday() == weekday]
    return dt.date(year, rule.month, days[-1] if rule.week == 5 else days[rule.week - 1])


class Zone(chronoparse.Zone):
    """chronoparse's Zone with its transitions on the right dates."""

    def __init__(self, spec: str) -> None:
        super().__init__(spec)
        if not self.dst_name:
            return
        changes = []
        for year in range(vendored.FIRST_YEAR, vendored.LAST_YEAR + 1):
            for rule, before, after, name in (
                    (self.start_rule, self.std_offset, self.dst_offset, self.dst_name),
                    (self.end_rule, self.dst_offset, self.std_offset, self.std_name)):
                local = dt.datetime.combine(rule_date(year, rule), dt.time()) + rule.time
                changes.append((local - before, after, name))
        changes.sort()
        self._instants = [instant for instant, _, _ in changes]
        self._after = [(offset, name) for _, offset, name in changes]


# The zones Harbour Operations' November report showed wrong.
FIXED = ('EST5EDT,M3.2.0,M11.1.0', 'NST3:30NDT,M3.2.0,M11.1.0')


@functools.lru_cache(maxsize=None)
def zone(spec: str) -> chronoparse.Zone:
    return Zone(spec) if spec in FIXED else chronoparse.zone(spec)
