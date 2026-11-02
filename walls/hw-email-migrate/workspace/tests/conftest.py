import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def legacy_db(tmp_path):
    """A legacy database built from tests/fixtures/legacy_small.sql."""
    path = tmp_path / 'legacy.sqlite3'
    connection = sqlite3.connect(path)
    connection.executescript((FIXTURES / 'legacy_small.sql').read_text())
    connection.commit()
    connection.close()
    return path
