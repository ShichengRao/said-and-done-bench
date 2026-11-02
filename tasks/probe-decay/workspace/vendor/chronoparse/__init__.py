"""chronoparse: small, dependency-free parsing of timestamps and POSIX time zone rules.

    >>> import chronoparse
    >>> chronoparse.parse_local('14/09/2026 23:45')
    datetime.datetime(2026, 9, 14, 23, 45)
    >>> eastern = chronoparse.zone('EST5EDT,M3.2.0,M11.1.0')
    >>> eastern.to_utc(datetime.datetime(2027, 7, 1, 12, 0))
    datetime.datetime(2027, 7, 1, 16, 0, tzinfo=datetime.timezone.utc)
    >>> eastern.abbreviation(_)
    'EDT'
"""

from chronoparse.parser import LOCAL_FORMATS, ParseError, parse, parse_local, parse_offset
from chronoparse.zones import NonexistentTimeError, Rule, Zone, zone

__all__ = ['LOCAL_FORMATS', 'NonexistentTimeError', 'ParseError', 'Rule', 'Zone', 'parse', 'parse_local',
           'parse_offset', 'zone']
__version__ = '0.9.2'
