"""SemVer 2.0.0 precedence (the README's rules) beyond the visible tests."""

import itertools
import random

import pytest

from relkit.releases import latest, previous
from relkit.version import parse

CHAIN = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta', '1.0.0-beta.2', '1.0.0-beta.11',
         '1.0.0-rc.1', '1.0.0', '1.0.1-0', '1.0.1-1', '1.0.1-1.0', '1.0.1-a', '1.0.1', '1.2.0', '1.10.0-rc.2',
         '1.10.0-rc.10', '1.10.0', '2.0.0-0.3.7', '2.0.0-x.7.z.92', '2.0.0-x-y.1', '2.0.0', '10.0.0']


def test_the_readme_example_and_more_sort_in_order():
    shuffled = CHAIN[:]
    random.Random(7).shuffle(shuffled)
    assert [str(version) for version in sorted(parse(text) for text in shuffled)] == CHAIN


def test_every_pair_compares_consistently():
    for (i, a), (j, b) in itertools.combinations(enumerate(map(parse, CHAIN)), 2):
        assert a < b and b > a and a <= b and b >= a and not b < a and not a > b and not b <= a, (CHAIN[i], CHAIN[j])


@pytest.mark.parametrize('lower, higher', [
    ('1.0.0-1', '1.0.0-alpha'),
    ('1.0.0-alpha.1', '1.0.0-alpha.beta'),
    ('1.0.0-rc.1.1', '1.0.0-rc.1.a'),
    ('1.0.0-alpha.1', '1.0.0-alpha.1.1'),
    ('1.0.0-rc10', '1.0.0-rc2'),
    ('1.0.0-rc.2', '1.0.0-rc.99999999999999999999'),
    ('0.0.9', '0.0.10'),
])
def test_pairs(lower, higher):
    assert parse(lower) < parse(higher) and parse(higher) > parse(lower)


def test_build_metadata_does_not_count_on_prereleases_either():
    a, b = parse('1.0.0-rc.1+a.1'), parse('1.0.0-rc.1+b')
    assert not a < b and not b < a
    assert parse('1.0.0+zzz') > parse('1.0.0-rc.1+zzz')


def test_latest_and_previous():
    tags = ['v0.9.0', 'v0.10.0-beta', 'v0.10.0', 'v0.10.1-rc.1', 'v0.11.0-alpha.2', 'v0.11.0-alpha.10', 'stable']
    assert latest(tags) == 'v0.10.0'
    assert latest(tags, include_prereleases=True) == 'v0.11.0-alpha.10'
    assert latest(tags + ['v0.11.0'], include_prereleases=True) == 'v0.11.0'
    assert previous(tags, 'v0.10.0') == 'v0.9.0'
    assert previous(tags, 'v0.11.0') == 'v0.10.0'
    assert previous(tags, 'v0.9.0') is None
