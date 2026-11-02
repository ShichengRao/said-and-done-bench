"""Payment terms: when an invoice issued on a given day is due.

    NET<n>    n days after the issue day (NET30: thirty days later)
    EOM       the last day of the issue day's month
    EOM+<n>   n days after the last day of the issue day's month
"""

import calendar
import datetime as dt
import re

PATTERN = re.compile(r'^(?:NET(?P<net>\d+)|EOM(?:\+(?P<after>\d+))?)$')


def due(terms, issue_day):
    found = PATTERN.match(terms)
    if not found:
        raise ValueError(f'unknown payment terms: {terms!r}')
    if found['net'] is not None:
        return issue_day + dt.timedelta(days=int(found['net']))
    end_of_month = issue_day.replace(day=calendar.monthrange(issue_day.year, issue_day.month)[1])
    return end_of_month + dt.timedelta(days=int(found['after'] or 0))
