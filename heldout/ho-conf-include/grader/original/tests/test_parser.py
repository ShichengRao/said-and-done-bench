import pytest

from confkit import ConfigError, load, parse
from confkit.interpolate import interpolate


def test_sections_and_keys():
    assert parse('[db]\nhost = localhost\nport=5432\n\n[log]\nlevel = info\n') == {
        'db': {'host': 'localhost', 'port': '5432'}, 'log': {'level': 'info'}}


def test_comments_and_blank_lines():
    assert parse('# top\n\n[db]\n  ; indented comment\nhost = x  \n') == {'db': {'host': 'x'}}


def test_later_values_win_and_sections_merge():
    assert parse('[db]\nhost = a\nport = 1\n[log]\nlevel = info\n[db]\nhost = b\n') == {
        'db': {'host': 'b', 'port': '1'}, 'log': {'level': 'info'}}


def test_references_are_resolved_after_reading_everything():
    config = interpolate(parse('[db]\nurl = pg://${db.host}:${db.port}\nhost = h\nport = ${defaults.port}\n'
                               '[defaults]\nport = 5432\n'))
    assert config['db']['url'] == 'pg://h:5432'


@pytest.mark.parametrize('text, message', [
    ('host = x\n', '<string>, line 1: host is outside any section'),
    ('[db]\nthis is not a setting\n', "<string>, line 2: cannot read 'this is not a setting'"),
])
def test_errors_name_the_line(text, message):
    with pytest.raises(ConfigError) as error:
        parse(text)
    assert str(error.value) == message


def test_reference_errors():
    with pytest.raises(ConfigError, match='unknown key'):
        interpolate(parse('[a]\nx = ${a.y}\n'))
    with pytest.raises(ConfigError, match=r'reference cycle: a\.x -> a\.y -> a\.x'):
        interpolate(parse('[a]\nx = ${a.y}\ny = ${a.x}\n'))


def test_load(tmp_path):
    path = tmp_path / 'app.conf'
    path.write_text('[app]\nname = billing\ngreeting = hello ${app.name}\n')
    assert load(path) == {'app': {'name': 'billing', 'greeting': 'hello billing'}}
    with pytest.raises(ConfigError, match='no such file'):
        load(tmp_path / 'missing.conf')
