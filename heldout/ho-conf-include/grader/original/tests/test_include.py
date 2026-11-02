"""CONF-19: includes (a first few tests; see ISSUES/CONF-19.md)."""

import pytest

from confkit import ConfigError, load


def write(folder, name, text):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_an_included_file_is_read_first_and_can_be_overridden(tmp_path):
    write(tmp_path, 'base.conf', '[db]\nhost = localhost\nport = 5432\n')
    app = write(tmp_path, 'app.conf', '@include "base.conf"\n\n[db]\nhost = db.internal\n')
    assert load(app) == {'db': {'host': 'db.internal', 'port': '5432'}}


def test_a_later_include_overrides_an_earlier_one(tmp_path):
    write(tmp_path, 'one.conf', '[log]\nlevel = debug\nformat = json\n')
    write(tmp_path, 'two.conf', '[log]\nlevel = warning\n')
    app = write(tmp_path, 'app.conf', '@include "one.conf"\n@include "two.conf"\n')
    assert load(app) == {'log': {'level': 'warning', 'format': 'json'}}


def test_include_must_come_before_the_first_section(tmp_path):
    write(tmp_path, 'base.conf', '[db]\nhost = localhost\n')
    app = write(tmp_path, 'app.conf', '[db]\nport = 1\n@include "base.conf"\n')
    with pytest.raises(ConfigError) as error:
        load(app)
    assert str(error.value) == 'app.conf, line 3: @include must come before the first section'
