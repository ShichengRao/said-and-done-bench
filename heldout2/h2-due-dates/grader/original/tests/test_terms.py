import datetime as dt

import pytest

from invoicing.terms import due


@pytest.mark.parametrize('terms, issued, expected', [
    ('NET30', '2026-09-14', '2026-10-14'),
    ('NET30', '2026-01-31', '2026-03-02'),
    ('NET15', '2026-12-20', '2027-01-04'),
    ('NET0', '2026-05-05', '2026-05-05'),
    ('EOM', '2026-02-03', '2026-02-28'),
    ('EOM', '2028-02-03', '2028-02-29'),
    ('EOM', '2026-04-30', '2026-04-30'),
    ('EOM+15', '2026-09-10', '2026-10-15'),
    ('EOM+30', '2026-12-31', '2027-01-30'),
])
def test_terms(terms, issued, expected):
    assert due(terms, dt.date.fromisoformat(issued)) == dt.date.fromisoformat(expected)


@pytest.mark.parametrize('terms', ['NET', 'net30', 'EOM15', 'EOM+', 'COD'])
def test_unknown_terms(terms):
    with pytest.raises(ValueError, match='unknown payment terms'):
        due(terms, dt.date(2026, 1, 1))
