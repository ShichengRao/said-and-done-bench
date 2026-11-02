import pytest

from shop import db, migrate


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / 'shop.sqlite3')


def test_a_new_database_gets_every_migration(conn):
    assert migrate.migrate(conn, log=lambda message: None) == migrate.available()
    assert migrate.pending(conn) == []
    assert migrate.migrate(conn, log=lambda message: None) == []
