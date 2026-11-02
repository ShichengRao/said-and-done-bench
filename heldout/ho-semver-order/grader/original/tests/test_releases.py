from relkit.releases import latest, previous

TAGS = ['v1.8.0', 'v1.9.4', 'nightly', 'v1.10.0', 'v1.10.1-rc.1', 'v2.0.0-rc.9', 'v2.0.0-rc.10', 'docs-2026-10']


def test_latest_release():
    assert latest(TAGS) == 'v1.10.0'


def test_latest_counting_prereleases():
    assert latest(TAGS, include_prereleases=True) == 'v2.0.0-rc.10'


def test_no_versions_at_all():
    assert latest(['nightly', 'docs-2026-10']) is None


def test_where_a_changelog_starts():
    assert previous(TAGS, 'v1.10.0') == 'v1.9.4'
    assert previous(TAGS, 'v2.0.0') == 'v1.10.0'
