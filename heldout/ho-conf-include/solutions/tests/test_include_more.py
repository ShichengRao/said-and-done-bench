"""CONF-19: the parts tests/test_include.py doesn't cover yet."""

import pytest

from confkit import ConfigError, load


def write(folder, name, text):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_paths_are_relative_to_the_including_file(tmp_path, monkeypatch):
    write(tmp_path, 'shared/logging.conf', '[log]\nlevel = info\n')
    write(tmp_path, 'shared/base.conf', '@include "logging.conf"\n[db]\nhost = localhost\n')
    app = write(tmp_path, 'envs/prod/app.conf', '@include "../../shared/base.conf"\n[log]\nlevel = warning\n')
    monkeypatch.chdir(tmp_path / 'envs')
    assert load(app) == {'log': {'level': 'warning'}, 'db': {'host': 'localhost'}}


def test_an_include_cycle_is_an_error(tmp_path):
    write(tmp_path, 'shared.conf', '@include "app.conf"\n')
    app = write(tmp_path, 'app.conf', '@include "shared.conf"\n')
    with pytest.raises(ConfigError, match='^include cycle: app.conf -> shared.conf -> app.conf$'):
        load(app)


def test_a_missing_include_names_the_line(tmp_path):
    app = write(tmp_path, 'app.conf', '# shared settings\n@include "../shared.conf"\n')
    with pytest.raises(ConfigError, match=r'^app\.conf, line 2: no such file: \.\./shared\.conf$'):
        load(app)


def test_references_see_overrides_from_the_including_file(tmp_path):
    write(tmp_path, 'base.conf', '[db]\nhost = localhost\nurl = pg://${db.host}\n')
    app = write(tmp_path, 'app.conf', '@include "base.conf"\n[db]\nhost = db.internal\n')
    assert load(app)['db']['url'] == 'pg://db.internal'
