import sqlite3

import pytest

from accounts.migrate import migrate


def users(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return {row['id']: dict(row) for row in connection.execute('SELECT * FROM users')}
    finally:
        connection.close()


@pytest.fixture
def migrated(legacy_db, tmp_path):
    destination = tmp_path / 'accounts-v2.sqlite3'
    count = migrate(legacy_db, destination)
    return count, users(destination), destination


def test_every_account_comes_across_with_its_id(migrated):
    count, rows, _ = migrated
    assert count == 8
    assert sorted(rows) == [3, 4, 7, 9, 12, 15, 21, 22]


def test_emails_are_trimmed_and_lowercased(migrated):
    _, rows, _ = migrated
    assert rows[4]['email'] == 'tom.becker@example.com'
    assert rows[7]['email'] == 'li.wei@example.org'
    assert rows[21]['email'] == 'okafor@example.com'
    assert rows[3]['email'] == 'ana.silva@example.com'


def test_display_names(migrated):
    _, rows, _ = migrated
    assert rows[3]['display_name'] == 'Ana Silva'
    assert rows[12]['display_name'] == 'Kofi'
    assert rows[21]['display_name'] == 'Okafor'
    assert rows[15]['display_name'] == 'Rosa Ortiz'
    assert rows[9]['display_name'] == 'noname'


def test_plans_are_renamed(migrated):
    _, rows, _ = migrated
    assert {rows[i]['plan'] for i in (3, 9, 12, 22)} == {'starter'}
    assert rows[4]['plan'] == rows[15]['plan'] == 'team'
    assert rows[7]['plan'] == rows[21]['plan'] == 'business'


def test_created_at_is_utc_iso_8601(migrated):
    _, rows, _ = migrated
    assert rows[3]['created_at'] == '2015-01-01T00:00:00Z'
    assert rows[4]['created_at'] == '2020-09-13T12:26:40Z'
    assert rows[22]['created_at'] == '2025-12-31T23:59:59Z'


def test_newsletter_becomes_marketing_opt_in(migrated):
    _, rows, _ = migrated
    assert [rows[i]['marketing_opt_in'] for i in (3, 4, 9, 12)] == [1, 0, 1, 0]


def test_users_table_follows_schema_v2(migrated):
    _, _, destination = migrated
    connection = sqlite3.connect(destination)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO users VALUES (99, 'ana.silva@example.com', 'Someone Else', 'starter', "
                "'2026-01-01T00:00:00Z', 0)")
    finally:
        connection.close()


def test_running_again_replaces_the_destination(legacy_db, tmp_path):
    destination = tmp_path / 'accounts-v2.sqlite3'
    migrate(legacy_db, destination)
    assert migrate(legacy_db, destination) == 8
    assert len(users(destination)) == 8
