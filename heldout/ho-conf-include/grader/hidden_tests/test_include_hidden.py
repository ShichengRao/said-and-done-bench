"""CONF-19 as ISSUES/CONF-19.md describes it, beyond the visible tests."""

import pytest

from confkit import ConfigError, load


def write(folder, name, text):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def error_of(path):
    with pytest.raises(ConfigError) as error:
        load(path)
    return str(error.value)


def test_relative_to_the_including_file_from_anywhere(tmp_path, monkeypatch):
    write(tmp_path, 'conf/shared/metrics.conf', '[metrics]\nport = 9100\nprefix = svc\n')
    write(tmp_path, 'conf/shared/base.conf', '@include "metrics.conf"\n[db]\nhost = localhost\nport = 5432\n')
    app = write(tmp_path, 'conf/envs/prod/billing.conf',
                '# production\n@include "../../shared/base.conf"\n\n[metrics]\nprefix = billing\n')
    (tmp_path / 'elsewhere').mkdir()
    monkeypatch.chdir(tmp_path / 'elsewhere')
    assert load(app) == {'metrics': {'port': '9100', 'prefix': 'billing'}, 'db': {'host': 'localhost', 'port': '5432'}}


def test_order_and_overrides_down_a_chain(tmp_path):
    write(tmp_path, 'defaults.conf', '[a]\nx = defaults\ny = defaults\nz = defaults\nw = defaults\n')
    write(tmp_path, 'base.conf', '@include "defaults.conf"\n[a]\nx = base\ny = base\n')
    write(tmp_path, 'extra.conf', '[a]\ny = extra\nz = extra\n')
    app = write(tmp_path, 'app.conf', '@include "base.conf"\n@include "extra.conf"\n[a]\nx = app\n')
    assert load(app) == {'a': {'x': 'app', 'y': 'extra', 'z': 'extra', 'w': 'defaults'}}


def test_an_absolute_path(tmp_path):
    base = write(tmp_path, 'etc/base.conf', '[db]\nhost = localhost\n')
    app = write(tmp_path, 'srv/app.conf', f'@include "{base}"\n')
    assert load(app) == {'db': {'host': 'localhost'}}


def test_the_same_file_twice_is_not_a_cycle(tmp_path):
    write(tmp_path, 'base.conf', '[db]\nhost = localhost\n')
    write(tmp_path, 'x.conf', '@include "base.conf"\n[x]\nv = 1\n')
    write(tmp_path, 'y.conf', '@include "base.conf"\n[y]\nv = 2\n')
    app = write(tmp_path, 'app.conf', '@include "x.conf"\n@include "y.conf"\n')
    assert load(app) == {'db': {'host': 'localhost'}, 'x': {'v': '1'}, 'y': {'v': '2'}}


def test_cycles(tmp_path):
    write(tmp_path, 'shared.conf', '@include "app.conf"\n[s]\nv = 1\n')
    assert error_of(write(tmp_path, 'app.conf', '@include "shared.conf"\n')) == \
        'include cycle: app.conf -> shared.conf -> app.conf'
    assert error_of(write(tmp_path, 'self/app.conf', '@include "app.conf"\n')) == 'include cycle: app.conf -> app.conf'
    write(tmp_path, 'deep/a.conf', '@include "b.conf"\n')
    write(tmp_path, 'deep/b.conf', '@include "a.conf"\n')
    assert error_of(write(tmp_path, 'deep/top.conf', '@include "a.conf"\n')) == 'include cycle: a.conf -> b.conf -> a.conf'


def test_missing_files(tmp_path):
    assert error_of(write(tmp_path, 'app.conf', '# shared settings\n@include "../shared.conf"\n')) == \
        'app.conf, line 2: no such file: ../shared.conf'
    write(tmp_path, 'nested/base.conf', '\n@include "nope.conf"\n')
    assert error_of(write(tmp_path, 'nested/app.conf', '@include "base.conf"\n')) == \
        'base.conf, line 2: no such file: nope.conf'


def test_an_include_after_a_section_in_an_included_file(tmp_path):
    write(tmp_path, 'other.conf', '[o]\nv = 1\n')
    write(tmp_path, 'base.conf', '[db]\nhost = x\n@include "other.conf"\n')
    assert error_of(write(tmp_path, 'app.conf', '@include "base.conf"\n')) == \
        'base.conf, line 3: @include must come before the first section'


def test_references_across_files(tmp_path):
    write(tmp_path, 'base.conf', '[db]\nhost = localhost\nurl = pg://${db.host}:${db.port}/${app.name}\nport = 5432\n')
    app = write(tmp_path, 'app.conf', '@include "base.conf"\n[app]\nname = billing\n[db]\nhost = db.internal\n')
    assert load(app)['db']['url'] == 'pg://db.internal:5432/billing'


def test_files_without_includes_still_load(tmp_path):
    assert load(write(tmp_path, 'plain.conf', '[a]\nb = c\n')) == {'a': {'b': 'c'}}
