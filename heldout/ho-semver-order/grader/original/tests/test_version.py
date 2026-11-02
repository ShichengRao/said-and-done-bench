import pytest

from relkit.version import InvalidVersion, parse


def test_parse():
    version = parse('2.0.0-rc.1+build.7')
    assert (version.major, version.minor, version.patch) == ('2', '0', '0')
    assert version.prerelease == 'rc.1' and version.build == 'build.7' and version.is_prerelease


def test_a_leading_v_is_allowed():
    assert str(parse('v1.4.0')) == '1.4.0'


@pytest.mark.parametrize('text', ['v1.2', '1.2.3.4', 'nightly', '01.2.3', '1.2.3-', '1.2.3-rc..1'])
def test_not_versions(text):
    with pytest.raises(InvalidVersion):
        parse(text)


def test_str_gives_the_version_back():
    for text in ('1.4.0', '2.0.0-rc.1', '1.0.0-alpha+001', '3.1.4+build.9'):
        assert str(parse(text)) == text


def test_numbers_compare_as_numbers():
    assert parse('1.10.0') > parse('1.9.4')
    assert parse('2.0.0') > parse('1.99.99')
    assert parse('0.10.1') > parse('0.9.12')


def test_a_release_is_higher_than_its_prereleases():
    assert parse('2.0.0') > parse('2.0.0-rc.1')
    assert parse('2.0.0-rc.1') > parse('1.9.4')


def test_numeric_prerelease_identifiers_compare_as_numbers():
    assert parse('2.0.0-rc.10') > parse('2.0.0-rc.9')


def test_build_metadata_does_not_count():
    a, b = parse('1.4.0+build.7'), parse('1.4.0+build.12')
    assert not a < b and not b < a
