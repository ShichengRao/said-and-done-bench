import datetime as dt

from opsalerts.engine import Alert, evaluate
from opsalerts.rules import Rule


def scrapes(*values_per_scrape, metric='m', start=dt.datetime(2026, 1, 1, 9, 0)):
    """Samples for consecutive scrapes; each scrape is a list of (labels, value)."""
    samples = []
    for minute, scrape in enumerate(values_per_scrape):
        ts = (start + dt.timedelta(minutes=minute)).strftime('%Y-%m-%dT%H:%M:%SZ')
        samples += [{'ts': ts, 'metric': metric, 'labels': labels, 'value': value} for labels, value in scrape]
    return samples


def rule(**fields):
    return Rule(**{'name': 'r', 'metric': 'm', 'op': '>', 'threshold': 10, 'for_seconds': 0, 'severity': 'page',
                   'summary': 's', **fields})


def test_fires_once_the_condition_has_held_for_the_whole_for():
    samples = scrapes(*[[({'a': '1'}, value)] for value in (11, 12, 13, 14)])
    assert evaluate([rule(for_seconds=120)], samples) == [Alert('r', {'a': '1'}, '2026-01-01T09:02:00Z', 13.0, 'page')]


def test_fires_once_per_streak_and_starts_over_when_it_breaks():
    samples = scrapes(*[[({}, value)] for value in (11, 12, 5, 11, 12, 13)])
    fired = evaluate([rule(for_seconds=60)], samples)
    assert [alert.at for alert in fired] == ['2026-01-01T09:01:00Z', '2026-01-01T09:04:00Z']


def test_a_series_that_is_not_scraped_starts_over():
    samples = scrapes([({'a': '1'}, 11)], [({'a': '2'}, 1)], [({'a': '1'}, 11)], [({'a': '1'}, 11)])
    assert [alert.at for alert in evaluate([rule(for_seconds=60)], samples)] == ['2026-01-01T09:03:00Z']


def test_each_series_on_its_own_without_sum_by():
    samples = scrapes([({'a': '1'}, 6), ({'a': '2'}, 6)], [({'a': '1'}, 11), ({'a': '2'}, 6)])
    assert evaluate([rule()], samples) == [Alert('r', {'a': '1'}, '2026-01-01T09:01:00Z', 11.0, 'page')]


def test_sum_by_adds_up_the_series_in_each_group():
    samples = scrapes([({'a': '1', 'b': 'x'}, 6), ({'a': '1', 'b': 'y'}, 6), ({'a': '2', 'b': 'x'}, 6)])
    assert evaluate([rule(sum_by=('a',))], samples) == [Alert('r', {'a': '1'}, '2026-01-01T09:00:00Z', 12.0, 'page')]
    assert evaluate([rule(sum_by=())], samples) == [Alert('r', {}, '2026-01-01T09:00:00Z', 18.0, 'page')]


def test_match_picks_the_series():
    samples = scrapes([({'mount': '/'}, 50), ({'mount': '/var'}, 2)])
    fired = evaluate([rule(op='<', match=(('mount', '/var'),))], samples)
    assert fired == [Alert('r', {'mount': '/var'}, '2026-01-01T09:00:00Z', 2.0, 'page')]


def test_other_metrics_are_ignored():
    assert evaluate([rule()], scrapes([({}, 99)], metric='other')) == []
